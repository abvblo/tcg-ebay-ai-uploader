"""Scryfall API Client for Magic: The Gathering cards"""

import aiohttp
import asyncio
from typing import Optional, Dict, Any, List
from ..utils.logger import logger

class ScryfallClient:
    def __init__(self, rate_limit: float = 0.1):
        self.base_url = "https://api.scryfall.com/cards/search"
        self.rate_limit = rate_limit
    
    async def get_card_data(self, card_name: str, set_name: str, 
                           session: aiohttp.ClientSession,
                           unique_characteristics: List[str] = None) -> Optional[Dict[str, Any]]:
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
                        
                        # For MTG, handle foil vs non-foil based on characteristics
                        is_foil = False
                        if unique_characteristics:
                            is_foil = any('foil' in char.lower() for char in unique_characteristics)
                        
                        prices = card.get('prices', {})
                        
                        # Select appropriate price
                        if is_foil and 'usd_foil' in prices:
                            usd_price = float(prices.get('usd_foil', 0) or 0)
                            logger.info(f"   💰 Using foil price: ${usd_price}")
                        else:
                            usd_price = float(prices.get('usd', 0) or 0)
                            logger.info(f"   💰 Using regular price: ${usd_price}")
                        
                        if usd_price > 0:
                            return self._format_card_data(card, usd_price)
                
                return None
                
        except Exception as e:
            logger.error(f"Scryfall API error: {e}")
            return None
    
    def _format_card_data(self, card: Dict[str, Any], market_price: float) -> Dict[str, Any]:
        """Format MTG card data"""
        # Scryfall provides purchase URLs
        purchase_urls = card.get('purchase_uris', {})
        tcgplayer_url = purchase_urls.get('tcgplayer', '')
        
        # Log what we're getting
        logger.info(f"   📊 Scryfall API - TCGPlayer data:")
        logger.info(f"      - Purchase URIs: {purchase_urls}")
        logger.info(f"      - TCGPlayer URL: {tcgplayer_url}")
        
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
            'data_source': 'Scryfall API',
            'tcgplayer_url': tcgplayer_url,  # Direct URL from API
            'tcgplayer_link': tcgplayer_url  # Also set as tcgplayer_link for consistency
        }