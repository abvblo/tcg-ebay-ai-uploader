"""Ximilar API Client"""

import aiohttp
import asyncio
from typing import Optional, Dict, Any
from ..utils.logger import logger

class XimilarClient:
    def __init__(self, api_key: str, endpoint: str, rate_limit: float = 0.1):
        self.api_key = api_key
        self.endpoint = endpoint
        self.rate_limit = rate_limit
    
    async def identify_card(self, image_url: str, session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
        """Identify card using Ximilar API"""
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {"records": [{"_url": image_url}]}
        
        # Rate limiting
        await asyncio.sleep(self.rate_limit)
        
        try:
            async with session.post(
                self.endpoint,
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    records = data.get("records", [])
                    if records:
                        return self._extract_card_data(records[0], image_url)
                else:
                    logger.error(f"❌ Ximilar API error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"❌ Ximilar API error: {e}")
            return None
    
    def _extract_card_data(self, ximilar_record: Dict[str, Any], image_url: str) -> Optional[Dict[str, Any]]:
        """Extract card data from Ximilar response"""
        if not ximilar_record:
            return None
        
        objects = ximilar_record.get("_objects", [])
        if not objects:
            return None
        
        card_obj = objects[0]
        identification = card_obj.get("_identification", {})
        
        # Check for errors
        if "error" in identification:
            logger.warning("⚠️ Card back detected - skipping")
            return None
        
        best_match = identification.get("best_match")
        if not best_match:
            return None
        
        # Extract core data
        name = best_match.get("name", "").strip()
        if not name:
            return None
        
        card_number = best_match.get("card_number", "")
        out_of = best_match.get("out_of", "")
        set_name = best_match.get("set", "").strip()
        rarity = best_match.get("rarity", "").strip()
        
        # FIX: Extract confidence from the correct location
        # Option 1: Use card detection probability (how confident it is that this is a card)
        card_detection_confidence = card_obj.get("prob", 0)
        
        # Option 2: Use match distance (how close the best match is)
        distances = identification.get("distances", [])
        match_confidence = 1 - distances[0] if distances else 0
        
        # Use card detection confidence as primary metric
        confidence = card_detection_confidence
        
        # Log both confidence metrics for debugging
        logger.debug(f"   🎯 Card Detection Confidence: {card_detection_confidence:.2%}")
        logger.debug(f"   📏 Match Distance: {distances[0] if distances else 'N/A'} (Match Confidence: {match_confidence:.2%})")
        
        # Clean name and extract unique characteristics
        clean_name, unique_characteristics = self._extract_unique_characteristics(name)
        
        return {
            'name': clean_name,
            'number': f"{card_number}/{out_of}" if card_number and out_of else card_number,
            'set_name': set_name,
            'rarity': rarity,
            'game': self._determine_game_type(set_name, name),
            'finish': self._determine_finish(rarity),
            'confidence': confidence,  # Now using the correct confidence value
            'match_confidence': match_confidence,  # Additional metric for reference
            'unique_characteristics': unique_characteristics,
            'source_image_url': image_url
        }
    
    def _extract_unique_characteristics(self, name: str) -> tuple[str, list[str]]:
        """Extract unique characteristics from card name"""
        unique_chars = []
        clean_name = name
        name_lower = name.lower()
        
        characteristics_map = {
            '1st edition': '1st Edition',
            'first edition': '1st Edition',
            'shadowless': 'Shadowless',
            'unlimited': 'Unlimited',
            'promo': 'Promo',
            'promotional': 'Promo',
            'staff': 'Staff',
            'stamped': 'Stamped',
            'error': 'Error',
            'misprint': 'Error',
            'pre-release': 'Pre-release',
            'prerelease': 'Pre-release'
        }
        
        for key, value in characteristics_map.items():
            if key in name_lower:
                if value == 'Unlimited' and '1st edition' in name_lower:
                    continue
                unique_chars.append(value)
                # Remove all variations of the characteristic
                for variant in [key, key.title(), key.upper(), value]:
                    clean_name = clean_name.replace(variant, '').strip()
        
        # Clean up double spaces
        clean_name = ' '.join(clean_name.split())
        
        return clean_name, unique_chars
    
    def _determine_game_type(self, set_name: str, card_name: str) -> str:
        """Determine game type from set name and card name"""
        combined_text = f"{set_name} {card_name}".lower()
        
        if any(indicator in combined_text for indicator in [
            'pokemon', 'pokémon', 'base set', 'jungle', 'fossil', 'gym', 'neo'
        ]):
            return 'Pokémon'
        elif any(indicator in combined_text for indicator in [
            'magic', 'mtg', 'alpha', 'beta', 'dominaria', 'zendikar'
        ]):
            return 'Magic: The Gathering'
        
        return 'Pokémon'
    
    def _determine_finish(self, rarity: str) -> str:
        """Determine finish from rarity"""
        if not rarity:
            return ''
        
        rarity_lower = rarity.lower()
        
        # Don't duplicate if already in rarity
        if any(term in rarity_lower for term in [
            'holo rare', 'secret rare', 'rainbow rare', 'gold rare', 
            'reverse holo', 'full art'
        ]):
            return ''
        
        # Extract finish if present
        if 'holo' in rarity_lower and 'rare' not in rarity_lower:
            return 'Holo'
        elif 'foil' in rarity_lower:
            return 'Foil'
        elif 'reverse' in rarity_lower:
            return 'Reverse Holo'
        
        return ''