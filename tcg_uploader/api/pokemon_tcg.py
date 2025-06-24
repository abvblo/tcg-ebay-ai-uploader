"""Pokemon TCG API Client"""

import aiohttp
import asyncio
from typing import Optional, Dict, Any
from ..utils.logger import logger

class PokemonTCGClient:
    def __init__(self, api_key: str, rate_limit: float = 0.05):
        self.api_key = api_key
        self.base_url = "https://api.pokemontcg.io/v2/cards"
        self.rate_limit = rate_limit
    
    async def get_card_data(self, card_name: str, set_name: str, 
                           session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
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
                        market_price = self._extract_price(card)
                        if market_price is not None:
                            return self._format_card_data(card, market_price)
                
                return None
                
        except Exception as e:
            logger.error(f"Pokemon TCG API error: {e}")
            return None
    
    def _extract_price(self, card: Dict[str, Any]) -> Optional[float]:
        """Extract price from Pokemon TCG data"""
        tcgplayer = card.get('tcgplayer', {})
        if not tcgplayer:
            return None
        
        prices = tcgplayer.get('prices', {})
        if not prices:
            return None
        
        # Try each price category
        for price_category, price_data in prices.items():
            if isinstance(price_data, dict) and 'market' in price_data:
                market_price = price_data.get('market')
                if market_price and float(market_price) > 0:
                    return float(market_price)
        
        return None
    
    def _format_card_data(self, card: Dict[str, Any], market_price: float) -> Dict[str, Any]:
        """Format Pokemon card data"""
        # Get the direct TCGPlayer URL from the API response
        tcgplayer_data = card.get('tcgplayer', {})
        tcgplayer_url = tcgplayer_data.get('url', '')
        
        # Log what we're getting from the API
        logger.info(f"   📊 Pokemon TCG API - TCGPlayer data:")
        logger.info(f"      - Full tcgplayer object: {tcgplayer_data}")
        logger.info(f"      - TCGPlayer URL: {tcgplayer_url}")
        
        return {
            'api_price': market_price,
            'price_source': 'Pokemon TCG API',
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