"""Scryfall API Client for Magic: The Gathering cards"""

import aiohttp
import asyncio
from typing import Optional, Dict, Any
from ..utils.logger import logger

class ScryfallClient:
    def __init__(self, rate_limit: float = 0.1):
        self.base_url = "https://api.scryfall.com/cards/search"
        self.rate_limit = rate_limit
    
    async def get_card_data(self, card_name: str, set_name: str, 
                           session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
        """Get card data from Scryfall API"""
        # Build search query
        search_query = f'name:"{card_name}"'
        if set_name and set_name.lower() != 'unknown':
            search_query += f' set:"{set_name}"'
        
        params = {
            'q': search_query,
            'format': 'json',
            'page': 1
        }
        
        # Rate limiting
        await asyncio.sleep(self.rate_limit)
        
        try:
            async with session.get(
                self.base_url,
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    cards = data.get('data', [])
                    
                    if cards:
                        card = cards[0]  # Take first match
                        usd_price = float(card.get('prices', {}).get('usd', 0) or 0)
                        
                        if usd_price > 0:
                            return self._format_card_data(card, usd_price)
                
                return None
                
        except Exception as e:
            logger.error(f"Scryfall API error: {e}")
            return None
    
    def _format_card_data(self, card: Dict[str, Any], market_price: float) -> Dict[str, Any]:
        """Format MTG card data"""
        return {
            'api_price': market_price,
            'price_source': 'Scryfall API',
            'scryfall_id': card.get('id'),
            'mana_cost': card.get('mana_cost', ''),
            'cmc': card.get('cmc', 0),
            'colors': card.get('colors', []),
            'color_identity': card.get('color_identity', []),
            'type_line': card.get('type_line', ''),
            'power': card.get('power'),
            'toughness': card.get('toughness'),
            'artist': card.get('artist'),
            'rarity_confirmed': card.get('rarity'),
            'set_confirmed': card.get('set_name'),
            'collector_number': card.get('collector_number'),
            'release_date': card.get('released_at'),
            'data_source': 'Scryfall API'
        }