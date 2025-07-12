"""Card identification and processing logic with retry and batch processing"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from tenacity import (
    RetryCallState,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from tqdm.asyncio import tqdm

from ..api.ebay_eps import EbayEPSUploader
from ..api.pokemon_tcg import PokemonTCGClient
from ..api.scryfall import ScryfallClient
from ..api.ximilar import XimilarClient
from ..cache import CacheManager
from ..config import Config
from ..database.optimized_service import OptimizedDatabaseService
from ..database.service import DatabaseService
from ..database.validator import DatabaseValidator
from ..models import CardData, ImageGroup
from ..utils.http_session import cleanup_sessions, get_optimized_session
from ..utils.logger import logger
from ..utils.metrics import MetricsTracker
from .price_calculator import PriceCalculator

# Configure retry logging
retry_logger = logging.getLogger("retry")


class RateLimitError(Exception):
    """Exception raised when rate limit is exceeded"""

    def __init__(self, message: str, retry_after: float = None):
        self.retry_after = retry_after
        super().__init__(message)


class CardIdentifier:
    """Handles card identification with retry logic and batch processing"""

    def __init__(self, config: Config, cache: CacheManager, metrics: MetricsTracker):
        self.config = config
        self.cache = cache
        self.metrics = metrics
        self._init_clients()
        self._init_validator()

    def _init_clients(self) -> None:
        """Initialize API clients with rate limiting and database integration"""
        # Initialize optimized database service for better performance
        self.db_service = OptimizedDatabaseService()

        self.ximilar = XimilarClient(
            self.config.ximilar_api_key,
            self.config.ximilar_endpoint,
            self.config.processing.rate_limit_ximilar,
        )
        self.pokemon_tcg = (
            PokemonTCGClient(
                self.config.pokemon_tcg_api_key,
                self.config.processing.rate_limit_pokemon,
            )
            if self.config.pokemon_tcg_api_key
            else None
        )

        self.scryfall = ScryfallClient(self.config.processing.rate_limit_scryfall)
        self.ebay_eps = EbayEPSUploader(
            self.config.ebay_config, self.config.processing.rate_limit_ebay
        )

        self.price_calculator = PriceCalculator(self.config.processing)

    def _init_validator(self) -> None:
        """Initialize database validator if available"""
        try:
            self.validator = DatabaseValidator()
            logger.info("✅ Database validator initialized")
        except Exception as e:
            logger.warning(f"⚠️ Database validator initialization failed: {e}")
            self.validator = None

    async def process_groups(self, image_groups: List[ImageGroup]) -> List[CardData]:
        """Process image groups with optimized connection pooling"""
        # Use optimized session with connection pooling
        async with get_optimized_session("card_processing") as session:
            results = await self._process_groups_with_session(image_groups, session)

        # Cleanup sessions after processing
        await cleanup_sessions()

        return results

    async def _process_groups_with_session(
        self, image_groups: List[ImageGroup], session: aiohttp.ClientSession
    ) -> List[CardData]:
        """Process image groups with an existing session"""
        semaphore = asyncio.Semaphore(self.config.processing.max_concurrent_groups)

        async def process_with_semaphore(group: ImageGroup) -> Optional[CardData]:
            async with semaphore:
                try:
                    return await self.process_single_group(group, session)
                except Exception as e:
                    logger.error(f"Error processing group {group.key}: {e}")
                    self.metrics.record_failed_card()
                    return None

        # Process in batches to show progress
        batch_size = min(10, self.config.processing.max_concurrent_groups)
        results = []

        with tqdm(total=len(image_groups), desc="Processing cards") as pbar:
            for i in range(0, len(image_groups), batch_size):
                batch = image_groups[i : i + batch_size]
                batch_results = await asyncio.gather(
                    *(process_with_semaphore(group) for group in batch), return_exceptions=True
                )

                # Filter out None results and exceptions
                valid_results = [r for r in batch_results if r and not isinstance(r, Exception)]
                results.extend(valid_results)

                # Update progress
                pbar.update(len(batch))

                # Log progress
                logger.info(
                    f"Processed {len(valid_results)}/{len(batch)} cards in batch {i//batch_size + 1}"
                )

        return results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, RateLimitError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def process_single_group(
        self, group: ImageGroup, session: aiohttp.ClientSession
    ) -> Optional[CardData]:
        """Process a single card group with retry logic"""
        try:
            # Only process front image for identification
            front_image = group.paths[group.front_idx]

            # Check cache first
            image_hash = self.cache.get_image_hash(front_image)
            cached_data = self.cache.get_cached_identification(image_hash)

            if cached_data:
                logger.debug(f"Cache hit for {group.key}")
                self.metrics.record_cache_hit("image")
                card_data = cached_data
            else:
                logger.debug(f"Cache miss for {group.key}, processing...")
                self.metrics.record_cache_miss("image")

                # Upload image to eBay EPS
                ebay_url = await self.ebay_eps.upload_image(front_image, session)
                if not ebay_url:
                    raise ValueError("Failed to upload image to eBay EPS")

                # Identify with Ximilar
                card_data = await self.identify_with_retry(ebay_url, session)

                # Validate and correct with database service
                card_data = self.db_service.validate_card_identification(card_data)

                # Store identification result in database
                card_id = self.db_service.store_identification_result(
                    card_data, card_data.get("confidence", 0.0), image_hash
                )
                if card_id:
                    card_data["database_card_id"] = card_id
                    logger.debug(f"💾 Stored identification result for {card_data.get('name')}")

                # Cache the result
                self.cache.cache_identification(image_hash, card_data)

            # Process card data
            return await self._process_card_data(card_data, group, session)

        except Exception as e:
            logger.error(f"Error in process_single_group: {e}")
            raise

    async def identify_with_retry(
        self, image_url: str, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Identify card with retry logic"""
        max_retries = self.config.processing.retry_attempts

        for attempt in range(max_retries):
            try:
                return await self.ximilar.identify_card(image_url, session)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise

                # Exponential backoff
                wait_time = 2**attempt
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)

        raise RuntimeError(f"Failed to identify card after {max_retries} attempts")

    async def _process_card_data(
        self, card_data: Dict[str, Any], group: ImageGroup, session: aiohttp.ClientSession
    ) -> CardData:
        """Process card data and generate final card information"""
        # Log identification
        confidence_pct = card_data.get("confidence", 0) * 100
        unique_chars = card_data.get("unique_characteristics", [])

        logger.info(
            f"📝 {card_data['name']} | {card_data.get('number', 'N/A')} | "
            f"{card_data.get('set_name', 'Unknown Set')} | "
            f"{card_data.get('rarity', 'Unknown Rarity')} | "
            f"Confidence: {confidence_pct:.1f}%"
        )

        if unique_chars:
            logger.info(f"   🎯 Unique characteristics: {', '.join(unique_chars)}")

        # Get pricing data (includes database caching)
        pricing_data = await self._get_pricing_data(card_data, session)

        # Calculate final price
        if pricing_data:
            api_price = pricing_data["api_price"]
            final_price = self.price_calculator.calculate_final_price(api_price)
            tcgplayer_link = pricing_data.get("tcgplayer_url", "") or pricing_data.get(
                "tcgplayer_link", ""
            )
            price_source = pricing_data.get("source", "unknown")

            # Store pricing data in database if we have a card ID
            if card_data.get("database_card_id"):
                price_storage_data = {
                    "prices": {"market": api_price},
                    "source": price_source,
                    "condition": "NM",
                    "currency": "USD",
                }
                self.db_service.store_price_data(card_data["database_card_id"], price_storage_data)
                logger.debug(f"💰 Stored pricing data for {card_data.get('name')}")
        else:
            final_price = self.price_calculator.calculate_final_price(5.00)
            tcgplayer_link = self._generate_tcgplayer_link(
                card_data["name"], card_data.get("set_name", ""), card_data.get("game", "Pokémon")
            )
            price_source = "default"
            logger.warning("   ⚠️ No pricing data found, using default price")

        # Upload all images
        image_urls = await self._upload_group_images(group, session)

        # Create and return CardData object
        return self._create_card_data(
            card_data=card_data,
            pricing_data=pricing_data or {},
            final_price=final_price,
            price_source=price_source,
            tcgplayer_link=tcgplayer_link,
            image_urls=image_urls,
            group=group,
        )

    async def _upload_group_images(
        self, group: ImageGroup, session: aiohttp.ClientSession
    ) -> List[str]:
        """Upload all images in a group"""
        upload_tasks = []
        for img_path in group.paths:
            upload_tasks.append(self.ebay_eps.upload_image(img_path, session))

        # Run uploads in parallel
        results = await asyncio.gather(*upload_tasks, return_exceptions=True)

        # Filter out failed uploads
        return [url for url in results if url and not isinstance(url, Exception)]

    async def _get_pricing_data(
        self, card_data: Dict[str, Any], session: aiohttp.ClientSession
    ) -> Optional[Dict[str, Any]]:
        """Get pricing data from appropriate API with caching"""
        cache_key = self._get_pricing_cache_key(card_data)
        cached_data = self.cache.get_cached_pricing(cache_key)

        if cached_data:
            self.metrics.record_cache_hit("pricing")
            return cached_data

        self.metrics.record_cache_miss("pricing")

        try:
            if card_data.get("game", "").lower() == "pokémon":
                pricing_data = await self._get_pokemon_pricing(card_data, session)
            else:
                pricing_data = await self._get_scryfall_pricing(card_data, session)

            if pricing_data:
                self.cache.cache_pricing(cache_key, pricing_data)

            return pricing_data

        except Exception as e:
            logger.error(f"Error getting pricing data: {e}")
            return None

    def _get_pricing_cache_key(self, card_data: Dict[str, Any]) -> str:
        """Generate a cache key for pricing data"""
        key_parts = [
            card_data.get("name", ""),
            card_data.get("set_name", ""),
            card_data.get("number", ""),
            card_data.get("finish", ""),
            card_data.get("language", "en"),
            ",".join(sorted(card_data.get("unique_characteristics", []))),
        ]
        return hashlib.md5("|".join(str(p) for p in key_parts).encode(), usedforsecurity=False).hexdigest()

    async def _get_pokemon_pricing(
        self, card_data: Dict[str, Any], session: aiohttp.ClientSession
    ) -> Optional[Dict[str, Any]]:
        """Get pricing data from Pokemon TCG API"""
        if not self.pokemon_tcg:
            return None

        try:
            return await self.pokemon_tcg.get_card_pricing(
                name=card_data["name"],
                set_name=card_data.get("set_name", ""),
                number=card_data.get("number", ""),
                session=session,
            )
        except Exception as e:
            logger.warning(f"Failed to get Pokemon pricing: {e}")
            return None

    async def _get_scryfall_pricing(
        self, card_data: Dict[str, Any], session: aiohttp.ClientSession
    ) -> Optional[Dict[str, Any]]:
        """Get pricing data from Scryfall API"""
        try:
            return await self.scryfall.get_card_pricing(
                name=card_data["name"],
                set_name=card_data.get("set_name", ""),
                collector_number=card_data.get("number", ""),
                session=session,
            )
        except Exception as e:
            logger.warning(f"Failed to get Scryfall pricing: {e}")
            return None

    def _create_card_data(
        self,
        card_data: Dict[str, Any],
        pricing_data: Dict[str, Any],
        final_price: float,
        price_source: str,
        tcgplayer_link: str,
        image_urls: List[str],
        group: ImageGroup,
    ) -> CardData:
        """Create a CardData object from processed data"""
        return CardData(
            name=card_data["name"],
            set_name=card_data.get("set_name", "Unknown Set"),
            number=card_data.get("number", ""),
            rarity=card_data.get("rarity", "Common"),
            game=card_data.get("game", "Pokémon"),
            confidence=card_data.get("confidence", 0.0),
            finish=card_data.get("finish", ""),
            unique_characteristics=card_data.get("unique_characteristics", []),
            language=card_data.get("language", "English"),
            api_price=pricing_data.get("api_price", 0.0),
            final_price=final_price,
            price_source=price_source,
            tcgplayer_link=tcgplayer_link,
            image_urls=image_urls,
            primary_image_url=image_urls[0] if image_urls else "",
            hp=card_data.get("hp"),
            types=card_data.get("types", []),
            subtypes=card_data.get("subtypes", []),
            artist=card_data.get("artist"),
            release_date=card_data.get("release_date"),
            power=card_data.get("power"),
            toughness=card_data.get("toughness"),
            card_size=card_data.get("card_size", "Standard"),
            is_variation_parent=False,
            variation_count=1,
            variations=[],
        )

    def _generate_tcgplayer_link(self, card_name: str, set_name: str, game: str = "Pokémon") -> str:
        """Generate a TCGPlayer search URL"""
        base_url = "https://shop.tcgplayer.com/"

        if game.lower() == "pokémon" or game.lower() == "pokemon":
            game_slug = "pokemon"
        elif "magic" in game.lower() or "mtg" in game.lower():
            game_slug = "magic"
        else:
            game_slug = game.lower()

        # Clean up card name and set name for URL
        clean_name = card_name.replace(" ", "-").replace("'", "").lower()
        clean_set = set_name.replace(" ", "-").replace("'", "").lower()

        return f"{base_url}{game_slug}/{clean_set}/{clean_name}"
