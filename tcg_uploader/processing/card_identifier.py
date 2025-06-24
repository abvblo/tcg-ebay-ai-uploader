"""Card identification and processing logic"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from tqdm.asyncio import tqdm

from ..models import ImageGroup, CardData
from ..config import Config
from ..cache import CacheManager
from ..api.ximilar import XimilarClient
from ..api.pokemon_tcg import PokemonTCGClient
from ..api.scryfall import ScryfallClient
from ..api.ebay_eps import EbayEPSUploader
from .price_calculator import PriceCalculator
from ..utils.logger import logger
from ..utils.metrics import MetricsTracker

class CardIdentifier:
    def __init__(self, config: Config, cache: CacheManager, metrics: MetricsTracker):
        self.config = config
        self.cache = cache
        self.metrics = metrics
        
        # Initialize API clients
        self.ximilar = XimilarClient(
            config.ximilar_api_key,
            config.ximilar_endpoint,
            config.processing.rate_limit_ximilar
        )
        self.pokemon_tcg = PokemonTCGClient(
            config.pokemon_tcg_api_key,
            config.processing.rate_limit_pokemon
        )
        self.scryfall = ScryfallClient(config.processing.rate_limit_scryfall)
        self.ebay_eps = EbayEPSUploader(config.ebay_config, config.processing.rate_limit_ebay)
        self.price_calculator = PriceCalculator(config.processing)
    
    async def process_groups(self, image_groups: List[ImageGroup]) -> List[CardData]:
        """Process all image groups"""
        # Create HTTP session
        connector = aiohttp.TCPConnector(limit=200, limit_per_host=60)
        timeout = aiohttp.ClientTimeout(total=45, connect=15, sock_read=90)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Process with controlled concurrency
            semaphore = asyncio.Semaphore(self.config.processing.max_concurrent_groups)
            
            async def process_with_semaphore(group: ImageGroup):
                async with semaphore:
                    return await self.process_single_group(group, session)
            
            # Create tasks
            tasks = [process_with_semaphore(group) for group in image_groups]
            
            # Process with progress bar
            results = []
            async for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Processing"):
                result = await coro
                if result:
                    results.append(result)
        
        return results
    
    async def process_single_group(self, group: ImageGroup, session: aiohttp.ClientSession) -> Optional[CardData]:
        """Process a single card group"""
        try:
            # Get front image for identification
            front_image = group.paths[group.front_idx]
            
            # Check cache first
            image_hash = self.cache.get_image_hash(front_image)
            cached_identification = self.cache.get_cached_identification(image_hash)
            
            if cached_identification:
                card_data = cached_identification
                self.metrics.record_cache_hit('image')
            else:
                # Upload to eBay EPS
                ebay_url = await self.ebay_eps.upload_image(front_image, session)
                if not ebay_url:
                    return None
                
                # Identify with Ximilar
                card_data = await self.ximilar.identify_card(ebay_url, session)
                if not card_data:
                    return None
                
                # Cache the result
                self.cache.cache_identification(image_hash, card_data)
                self.metrics.record_cache_miss('image')
                self.metrics.record_api_call('ximilar')
            
            # Log identification
            logger.info(f"\n📝 {card_data['name']} | {card_data['number']} | "
                       f"{card_data['set_name']} | {card_data['rarity']}")
            
            # Get pricing data
            pricing_data = await self._get_pricing_data(card_data, session)
            
            # Log what we got from pricing data
            if pricing_data:
                logger.info(f"   📊 Pricing data received:")
                logger.info(f"      - tcgplayer_url: {pricing_data.get('tcgplayer_url', 'None')}")
                logger.info(f"      - tcgplayer_link: {pricing_data.get('tcgplayer_link', 'None')}")
            
            # Calculate final price and handle TCGPlayer link
            if pricing_data:
                api_price = pricing_data['api_price']
                final_price = self.price_calculator.calculate_final_price(api_price)
                
                # Use the direct TCGPlayer URL from API
                tcgplayer_link = pricing_data.get('tcgplayer_url', '') or pricing_data.get('tcgplayer_link', '')
                
                logger.info(f"💰 TCGPlayer Price: ${api_price:.2f}")
                logger.info(f"📈 Final Price: ${final_price:.2f}")
                logger.info(f"🔗 Using TCGPlayer link: {tcgplayer_link}")
            else:
                final_price = self.price_calculator.calculate_final_price(5.00)
                
                # Generate search link as fallback
                tcgplayer_link = self._generate_tcgplayer_link(
                    card_data['name'],
                    card_data['set_name'],
                    card_data['game']
                )
                
                logger.info(f"💰 No market price found - using default")
                logger.info(f"📈 Final Price: ${final_price:.2f}")
                logger.info(f"🔗 Generated search link: {tcgplayer_link}")
            
            # Upload all images
            image_urls = await self._upload_all_images(group, session)
            if not image_urls:
                return None
            
            # Create CardData object
            result = self._create_card_data(card_data, pricing_data, final_price, image_urls, group)
            
            # Log the final TCGPlayer link in the CardData
            logger.info(f"   📦 Final CardData TCGPlayer link: {result.tcgplayer_link}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error processing {group.key}: {e}")
            self.metrics.record_failed_card()
            return None
    
    async def _get_pricing_data(self, card_data: Dict[str, Any], 
                               session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
        """Get pricing data from appropriate API"""
        card_name = card_data['name']
        set_name = card_data['set_name']
        game = card_data['game']
        
        # Check cache
        cached_data = self.cache.get_cached_card_data(card_name, set_name)
        if cached_data:
            logger.info(f"   💾 Using cached pricing data")
            logger.info(f"      - Cached tcgplayer_url: {cached_data.get('tcgplayer_url', 'None')}")
            logger.info(f"      - Cached tcgplayer_link: {cached_data.get('tcgplayer_link', 'None')}")
            self.metrics.record_cache_hit('card_data')
            return cached_data
        
        logger.info(f"   🔍 Fetching fresh pricing data from API")
        
        # Get from API
        if game == 'Pokémon':
            api_data = await self.pokemon_tcg.get_card_data(card_name, set_name, session)
        else:
            api_data = await self.scryfall.get_card_data(card_name, set_name, session)
        
        if api_data:
            # The API should have already set tcgplayer_url
            # We'll use it as tcgplayer_link for consistency
            if 'tcgplayer_url' in api_data and api_data['tcgplayer_url']:
                api_data['tcgplayer_link'] = api_data['tcgplayer_url']
            else:
                # Only fall back to search if no direct URL
                api_data['tcgplayer_link'] = self._generate_tcgplayer_link(card_name, set_name, game)
            
            # Cache the result
            self.cache.cache_card_data(card_name, set_name, api_data)
            self.metrics.record_cache_miss('card_data')
            self.metrics.record_api_call('pokemon_tcg' if game == 'Pokémon' else 'scryfall')
            
            return api_data
        
        return None
    
    async def _upload_all_images(self, group: ImageGroup, 
                                session: aiohttp.ClientSession) -> List[str]:
        """Upload all images in group to eBay EPS"""
        tasks = [self.ebay_eps.upload_image(path, session) for path in group.paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful uploads
        return [url for url in results if url and not isinstance(url, Exception)]
    
    def _create_card_data(self, identification: Dict[str, Any], 
                         pricing_data: Optional[Dict[str, Any]],
                         final_price: float,
                         image_urls: List[str],
                         group: ImageGroup) -> CardData:
        """Create CardData object from all information"""
        # Use the direct TCGPlayer URL from pricing data if available
        tcgplayer_link = ''
        if pricing_data:
            # First try tcgplayer_url (direct link), then tcgplayer_link
            tcgplayer_link = pricing_data.get('tcgplayer_url', '') or pricing_data.get('tcgplayer_link', '')
        
        if not tcgplayer_link:
            # Only generate search link as absolute fallback
            tcgplayer_link = self._generate_tcgplayer_link(
                identification['name'],
                identification['set_name'], 
                identification['game']
            )
        
        card_data = CardData(
            name=identification['name'],
            set_name=identification['set_name'],
            number=identification['number'],
            rarity=identification['rarity'],
            game=identification['game'],
            confidence=identification['confidence'],
            finish=identification.get('finish', ''),
            unique_characteristics=identification.get('unique_characteristics', []),
            api_price=pricing_data.get('api_price', 5.00) if pricing_data else 5.00,
            final_price=final_price,
            price_source=pricing_data.get('price_source', 'Default') if pricing_data else 'Default',
            tcgplayer_link=tcgplayer_link,  # Use the direct link
            image_urls=image_urls,
            primary_image_url=image_urls[0] if image_urls else ''
        )
        
        # Add additional data if available
        if pricing_data:
            card_data.hp = pricing_data.get('hp')
            card_data.types = pricing_data.get('types', [])
            card_data.subtypes = pricing_data.get('subtypes', [])
            card_data.artist = pricing_data.get('artist')
        
        # Determine review flag
        card_data.review_flag = self._determine_review_flag(card_data)
        if card_data.review_flag != 'OK':
            logger.info(f"⚠️ Review needed: {card_data.review_flag}")
        
        return card_data
    
    def _determine_review_flag(self, card_data: CardData) -> str:
        """Determine if card needs review"""
        if not card_data.name:
            return 'MISSING_DATA'
        
        if card_data.name.isdigit() or len(card_data.name) == 1:
            return 'OCR_ERROR'
        
        if card_data.confidence < 0.30:
            return 'LOW_CONFIDENCE'
        
        return 'OK'
    
    def _generate_tcgplayer_link(self, card_name: str, set_name: str, game: str) -> str:
        """Generate TCGPlayer search link (fallback only)"""
        import re
        
        clean_name = re.sub(r'[^\w\s-]', '', card_name).strip().replace(' ', '%20')
        clean_set = re.sub(r'[^\w\s-]', '', set_name).strip().replace(' ', '%20')
        
        if game.lower() in ['pokémon', 'pokemon']:
            base_url = "https://www.tcgplayer.com/search/pokemon/product"
        elif game.lower() in ['magic: the gathering', 'mtg']:
            base_url = "https://www.tcgplayer.com/search/magic/product"
        else:
            return f"https://www.tcgplayer.com/search/all/product?q={clean_name}"
        
        search_params = f"?q={clean_name}"
        if clean_set:
            search_params += f"&setName={clean_set}"
        
        return base_url + search_params