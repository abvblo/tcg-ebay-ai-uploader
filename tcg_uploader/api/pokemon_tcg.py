"""Pokemon TCG API Client"""

import aiohttp
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from ..utils.logger import logger
from ..price_mappings import PriceMappingConfig

class PokemonTCGClient:
    def __init__(self, api_key: str, rate_limit: float = 0.05):
        self.api_key = api_key
        self.base_url = "https://api.pokemontcg.io/v2/cards"
        self.rate_limit = rate_limit
        self.price_config = PriceMappingConfig()
    
    async def get_card_data(self, card_name: str, set_name: str, 
                           session: aiohttp.ClientSession,
                           unique_characteristics: List[str] = None,
                           language: str = 'English') -> Optional[Dict[str, Any]]:
        """Get card data from Pokemon TCG API"""
        # Build search query
        search_parts = [f'name:"{card_name}"']
        if set_name and set_name.lower() != 'unknown':
            search_parts.append(f'set.name:"{set_name}"')
        
        params = {
            "q": ' '.join(search_parts),
            "pageSize": 5,
            "orderBy": "-set.releaseDate"
        }
        
        headers = {"X-Api-Key": self.api_key} if self.api_key else {}
        
        # Rate limiting
        await asyncio.sleep(self.rate_limit)
        
        try:
            async with session.get(
                self.base_url,
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    cards = data.get('data', [])
                    
                    for card in cards:
                        market_price, price_category = self._extract_price_with_category(
                            card, unique_characteristics, language
                        )
                        if market_price is not None:
                            return self._format_card_data(card, market_price, price_category)
                
                return None
                
        except Exception as e:
            logger.error(f"Pokemon TCG API error: {e}")
            return None
    
    def _extract_price_with_category(self, card: Dict[str, Any], 
                                    unique_characteristics: List[str] = None,
                                    language: str = 'English') -> Tuple[Optional[float], Optional[str]]:
        """Extract price from Pokemon TCG data based on card characteristics"""
        tcgplayer = card.get('tcgplayer', {})
        if not tcgplayer:
            return None, None
        
        prices = tcgplayer.get('prices', {})
        if not prices:
            return None, None
        
        # Log available price categories
        logger.info(f"   💳 Available price categories: {list(prices.keys())}")
        
        # Determine price categories to check based on characteristics
        priority_categories = self._determine_price_categories(
            unique_characteristics, language, list(prices.keys()), 
            card.get('set', {}).get('name')
        )
        
        # Log what we're looking for
        chars_str = ', '.join(unique_characteristics) if unique_characteristics else 'None'
        logger.info(f"   🎯 Card characteristics: {chars_str}")
        logger.info(f"   🔍 Checking price categories in order: {priority_categories[:5]}...")
        
        # Try to find a price using the priority order
        for price_key in priority_categories:
            if price_key in prices:
                price_data = prices[price_key]
                if isinstance(price_data, dict):
                    # Try different price fields in order of preference
                    for price_field in ['market', 'mid', 'low']:
                        if price_field in price_data:
                            price_value = price_data.get(price_field)
                            if price_value and float(price_value) > 0:
                                logger.info(f"   💰 Using {price_field} price from '{price_key}': ${price_value}")
                                return float(price_value), price_key
        
        # Final fallback: Use ANY available price (but warn about it)
        logger.warning("   ⚠️ No matching price category found, using first available price")
        for price_category, price_data in prices.items():
            if isinstance(price_data, dict):
                for price_field in ['market', 'mid', 'low']:
                    if price_field in price_data:
                        price_value = price_data.get(price_field)
                        if price_value and float(price_value) > 0:
                            logger.info(f"   💰 Fallback {price_field} price from '{price_category}': ${price_value}")
                            return float(price_value), price_category
        
        return None, None
    
    def _determine_price_categories(self, unique_characteristics: List[str] = None,
                                   language: str = 'English',
                                   available_categories: List[str] = None,
                                   set_name: str = None) -> List[str]:
        """Determine which price categories to check based on card characteristics"""
        priority_categories = []
        
        # First, check for special combinations
        if unique_characteristics:
            combination_categories = self.price_config.get_combination_categories(unique_characteristics)
            priority_categories.extend(combination_categories)
        
        # Process individual characteristics
        if unique_characteristics:
            for characteristic in unique_characteristics:
                categories = self.price_config.get_mapping(characteristic)
                priority_categories.extend(categories)
        
        # Handle language-specific categories
        if language and language.lower() != 'english':
            lang_categories = self.price_config.get_mapping(language)
            priority_categories.extend(lang_categories)
        
        # Add default categories
        priority_categories.extend(self.price_config.DEFAULT_CATEGORIES)
        
        # Apply set-specific rules
        if set_name:
            priority_categories = self.price_config.apply_set_rules(set_name, priority_categories)
        
        # Apply exclusion rules
        priority_categories = self.price_config.apply_exclusion_rules(
            unique_characteristics or [], priority_categories
        )
        
        # Remove duplicates while preserving order
        seen = set()
        unique_categories = []
        for cat in priority_categories:
            if cat not in seen:
                seen.add(cat)
                unique_categories.append(cat)
        
        # Filter to only available categories if provided
        if available_categories:
            available_set = set(available_categories)
            unique_categories = [cat for cat in unique_categories if cat in available_set]
        
        return unique_categories
    
    def _format_card_data(self, card: Dict[str, Any], market_price: float, 
                         price_category: str) -> Dict[str, Any]:
        """Format Pokemon card data"""
        # Get the direct TCGPlayer URL from the API response
        tcgplayer_data = card.get('tcgplayer', {})
        tcgplayer_url = tcgplayer_data.get('url', '')
        
        # Log what we're getting from the API
        logger.info(f"   📊 Pokemon TCG API - Final data:")
        logger.info(f"      - Price category used: {price_category}")
        logger.info(f"      - Market price: ${market_price}")
        logger.info(f"      - TCGPlayer URL: {tcgplayer_url}")
        
        return {
            'api_price': market_price,
            'price_source': f'Pokemon TCG API ({price_category})',
            'price_category': price_category,
            'pokemon_tcg_id': card.get('id'),
            'hp': str(card.get('hp', '')),
            'types': card.get('types', []),
            'subtypes': card.get('subtypes', []),
            'supertype': card.get('supertype'),
            'artist': card.get('artist'),
            'rarity_confirmed': card.get('rarity'),
            'set_confirmed': card.get('set', {}).get('name'),
            'release_date': card.get('set', {}).get('releaseDate'),
            'data_source': 'Pokemon TCG API',
            'tcgplayer_url': tcgplayer_url,  # Direct URL from API
            'tcgplayer_link': tcgplayer_url  # Also set as tcgplayer_link for consistency
        }