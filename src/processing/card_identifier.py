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
            # Only process front image for identification (back is just for eBay listing)
            front_image = group.paths[group.front_idx]
            
            logger.debug(f"   🎴 Processing group with {len(group.paths)} images (front + back)")
            
            # Check cache first
            image_hash = self.cache.get_image_hash(front_image)
            cached_identification = self.cache.get_cached_identification(image_hash)
            
            if cached_identification:
                card_data = cached_identification
                self.metrics.record_cache_hit('image')
            else:
                # Upload ONLY front image to eBay EPS for Ximilar identification
                ebay_url = await self.ebay_eps.upload_image(front_image, session)
                if not ebay_url:
                    logger.error(f"   ❌ Failed to upload front image to eBay EPS")
                    return None
                
                # Identify with Ximilar (only using front image)
                card_data = await self.ximilar.identify_card(ebay_url, session)
                if not card_data:
                    logger.error(f"   ❌ Ximilar failed to identify card from front image")
                    return None
                
                # Cache the result
                self.cache.cache_identification(image_hash, card_data)
                self.metrics.record_cache_miss('image')
                self.metrics.record_api_call('ximilar')
            
            # Log identification WITH CONFIDENCE
            unique_chars_str = ', '.join(card_data.get('unique_characteristics', [])) if card_data.get('unique_characteristics') else 'None'
            confidence_pct = card_data.get('confidence', 0) * 100
            
            logger.info(f"\n📝 {card_data['name']} | {card_data['number']} | "
                       f"{card_data['set_name']} | {card_data['rarity']} | "
                       f"Confidence: {confidence_pct:.1f}%")
            
            if unique_chars_str != 'None':
                logger.info(f"   🎯 Unique characteristics: {unique_chars_str}")
            
            # Get pricing data with unique characteristics
            pricing_data = await self._get_pricing_data(card_data, session)
            
            # Calculate final price
            if pricing_data:
                api_price = pricing_data['api_price']
                final_price = self.price_calculator.calculate_final_price(api_price)
                tcgplayer_link = pricing_data.get('tcgplayer_url', '') or pricing_data.get('tcgplayer_link', '')
                
                # Single consolidated price log
                logger.info(f"   💰 Price: ${api_price:.2f} → ${final_price:.2f} (after {(self.price_calculator.markup_percentage-1)*100:.0f}% markup)")
            else:
                final_price = self.price_calculator.calculate_final_price(5.00)
                tcgplayer_link = self._generate_tcgplayer_link(
                    card_data['name'],
                    card_data['set_name'],
                    card_data['game']
                )
                logger.info(f"   💰 No market price found - using default ${final_price:.2f}")
            
            # Upload all images
            image_urls = await self._upload_all_images(group, session)
            if not image_urls:
                logger.error(f"   ❌ Failed to upload all images to eBay EPS")
                return None
            
            # Create CardData object
            result = self._create_card_data(card_data, pricing_data, final_price, image_urls, group)
            
            # Log review flag only if needed
            if result.review_flag != 'OK':
                logger.warning(f"   ⚠️ Review needed: {result.review_flag}")
            
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
        unique_characteristics = card_data.get('unique_characteristics', [])
        
        # Check cache
        cached_data = self.cache.get_cached_card_data(card_name, set_name)
        if cached_data:
            logger.info(f"   📦 Using cached pricing data")
            self.metrics.record_cache_hit('card_data')
            return cached_data
        
        logger.info(f"   🔍 Fetching pricing from {game} API...")
        
        # Get from API
        if game == 'Pokémon':
            # Pass unique characteristics and language to Pokemon TCG API
            api_data = await self.pokemon_tcg.get_card_data(
                card_name, 
                set_name, 
                session,
                unique_characteristics=unique_characteristics,
                language=card_data.get('language', 'English')
            )
        else:
            api_data = await self.scryfall.get_card_data(card_name, set_name, session, unique_characteristics)
        
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
        successful_urls = [url for url in results if url and not isinstance(url, Exception)]
        
        if len(successful_urls) < len(group.paths):
            logger.warning(f"   ⚠️ Only {len(successful_urls)}/{len(group.paths)} images uploaded successfully")
        
        return successful_urls
    
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
        
        # Use finish and features from API data if available, otherwise fall back to Ximilar
        finish = ''
        unique_characteristics = []
        
        if pricing_data:
            # Prefer API data for finish and features
            finish = pricing_data.get('finish_api', '') or identification.get('finish', '')
            unique_characteristics = pricing_data.get('features_api', []) or identification.get('unique_characteristics', [])
        else:
            # Fall back to Ximilar data
            finish = identification.get('finish', '')
            unique_characteristics = identification.get('unique_characteristics', [])
        
        # Format card number with total if available
        card_number = identification['number']
        if pricing_data:
            # Try to get confirmed number from API
            api_number = pricing_data.get('number_confirmed', '')
            if api_number:
                card_number = api_number
            
            # If we have set total, format as "number/total"
            set_total = pricing_data.get('set_total')
            if set_total and '/' not in str(card_number):
                # Only add total if not already in "number/total" format
                card_number = f"{card_number}/{set_total}"
        
        card_data = CardData(
            name=identification['name'],
            set_name=pricing_data.get('set_confirmed', identification['set_name']) if pricing_data else identification['set_name'],
            number=card_number,
            rarity=pricing_data.get('rarity_confirmed', identification['rarity']) if pricing_data else identification['rarity'],
            game=identification['game'],
            confidence=identification['confidence'],
            finish=finish,
            unique_characteristics=unique_characteristics,
            api_price=pricing_data.get('api_price', 5.00) if pricing_data else 5.00,
            final_price=final_price,
            price_source=pricing_data.get('price_source', 'Default') if pricing_data else 'Default',
            tcgplayer_link=tcgplayer_link,
            image_urls=image_urls,
            primary_image_url=image_urls[0] if image_urls else ''
        )
        
        # Add additional data if available from APIs
        if pricing_data:
            # Pokemon-specific data
            card_data.hp = pricing_data.get('hp')
            card_data.types = pricing_data.get('types', [])
            card_data.subtypes = pricing_data.get('subtypes', [])
            card_data.artist = pricing_data.get('artist')
            
            # IMPORTANT: Store release date for year extraction
            card_data.release_date = pricing_data.get('release_date')
            
            # Additional Pokemon data for features
            if pricing_data.get('abilities'):
                card_data.processing_notes = f"Abilities: {', '.join(pricing_data['abilities'])}"
            if pricing_data.get('evolves_from'):
                if card_data.processing_notes:
                    card_data.processing_notes += f" | Evolves from: {pricing_data['evolves_from']}"
                else:
                    card_data.processing_notes = f"Evolves from: {pricing_data['evolves_from']}"
            
            # MTG-specific data
            if identification['game'] == 'Magic: The Gathering':
                # MTG colors go into types for the eBay field mapping
                card_data.types = pricing_data.get('colors', [])
                # Type line info can go into subtypes
                type_line = pricing_data.get('type_line', '')
                if type_line:
                    card_data.subtypes = [type_line]
                
                # NEW: Extract power and toughness for creatures
                card_data.power = pricing_data.get('power')
                card_data.toughness = pricing_data.get('toughness')
                
                # Check if oversized
                if pricing_data.get('oversized', False):
                    card_data.card_size = 'Oversized'
        
        # Determine review flag
        card_data.review_flag = self._determine_review_flag(card_data)
        
        return card_data
    
    def _determine_review_flag(self, card_data: CardData) -> str:
        """Determine if card needs review"""
        if not card_data.name:
            return 'MISSING_DATA'
        
        if card_data.name.isdigit() or len(card_data.name) == 1:
            return 'OCR_ERROR'
        
        if card_data.confidence < self.config.processing.confidence_threshold_low:
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