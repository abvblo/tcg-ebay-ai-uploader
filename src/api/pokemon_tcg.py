"""Enhanced Pokemon TCG API Client with better matching logic"""

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
                           language: str = 'English',
                           card_number: str = None) -> Optional[Dict[str, Any]]:
        """Get card data from Pokemon TCG API with enhanced matching"""
        
        # Try multiple search strategies
        search_strategies = self._build_search_strategies(card_name, set_name, card_number)
        
        for strategy_name, params in search_strategies:
            logger.info(f"   🔍 Trying search strategy: {strategy_name}")
            
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
                        
                        # Find best match
                        best_match = self._find_best_match(cards, card_name, set_name, card_number)
                        
                        if best_match:
                            market_price, price_category = self._extract_near_mint_price(
                                best_match, unique_characteristics, language
                            )
                            if market_price is not None:
                                logger.info(f"   ✅ Found match with {strategy_name} strategy")
                                return self._format_card_data(best_match, market_price, price_category)
            
            except Exception as e:
                logger.error(f"Pokemon TCG API error with {strategy_name}: {e}")
                continue
        
        logger.warning(f"   ⚠️ No match found for {card_name} after trying all strategies")
        return None
    
    def _build_search_strategies(self, card_name: str, set_name: str, card_number: str = None) -> List[Tuple[str, Dict]]:
        """Build multiple search strategies for better matching"""
        strategies = []
        
        # Clean inputs
        clean_name = self._clean_card_name(card_name)
        clean_set = self._clean_set_name(set_name)
        
        # Strategy 1: Exact name and set search
        if clean_set and clean_set.lower() != 'unknown':
            strategies.append(("Exact name + set", {
                "q": f'name:"{card_name}" set.name:"{set_name}"',
                "pageSize": 10,
                "orderBy": "-set.releaseDate"
            }))
        
        # Strategy 2: Card number search (very reliable for promos)
        if card_number:
            # Extract just the number part (e.g., "SWSH283" from various formats)
            clean_number = self._clean_card_number(card_number)
            if clean_number:
                strategies.append(("Card number search", {
                    "q": f'number:{clean_number}',
                    "pageSize": 20,
                    "orderBy": "-set.releaseDate"
                }))
                
                # Also try with wildcards
                strategies.append(("Card number wildcard", {
                    "q": f'number:*{clean_number}*',
                    "pageSize": 20,
                    "orderBy": "-set.releaseDate"
                }))
        
        # Strategy 3: Name only search (broader)
        strategies.append(("Name only", {
            "q": f'name:"{clean_name}"',
            "pageSize": 15,
            "orderBy": "-set.releaseDate"
        }))
        
        # Strategy 4: Partial name search for complex names
        name_parts = clean_name.split()
        if len(name_parts) > 1:
            # Try first two words
            partial_name = ' '.join(name_parts[:2])
            strategies.append(("Partial name", {
                "q": f'name:"{partial_name}"',
                "pageSize": 20,
                "orderBy": "-set.releaseDate"
            }))
        
        # Strategy 5: Set-based search for promos
        if 'promo' in set_name.lower():
            strategies.append(("Promo search", {
                "q": f'name:"{clean_name}" set.name:*promo*',
                "pageSize": 20,
                "orderBy": "-set.releaseDate"
            }))
        
        return strategies
    
    def _clean_card_name(self, card_name: str) -> str:
        """Clean card name for better matching"""
        # Remove common suffixes that might interfere
        suffixes_to_remove = [' v', ' vmax', ' vstar', ' ex', ' gx', ' tag team']
        clean_name = card_name.lower()
        for suffix in suffixes_to_remove:
            if clean_name.endswith(suffix):
                clean_name = clean_name[:-len(suffix)]
                break
        
        # Remove special characters but keep spaces
        import re
        clean_name = re.sub(r'[^\w\s-]', '', card_name).strip()
        
        return clean_name
    
    def _clean_set_name(self, set_name: str) -> str:
        """Clean set name for better matching"""
        # Common set name variations to normalize
        set_mappings = {
            'sword shield promos': 'SWSH Black Star Promos',
            'swsh promos': 'SWSH Black Star Promos',
            'sword & shield promos': 'SWSH Black Star Promos',
            'sun moon promos': 'SM Black Star Promos',
            'sm promos': 'SM Black Star Promos',
            'xy promos': 'XY Black Star Promos',
            'black white promos': 'BW Black Star Promos',
            'bw promos': 'BW Black Star Promos',
        }
        
        lower_set = set_name.lower()
        for key, value in set_mappings.items():
            if key in lower_set:
                return value
        
        return set_name
    
    def _clean_card_number(self, card_number: str) -> str:
        """Extract clean card number for searching"""
        if not card_number:
            return ""
        
        # Remove common prefixes/suffixes
        import re
        
        # Handle different formats: "11/20", "SWSH283", "SM-P 283", etc.
        # First, check if it's a promo number
        promo_match = re.search(r'(SWSH|SM|XY|BW|DP|HGSS)\s*-?\s*P?\s*(\d+)', card_number, re.IGNORECASE)
        if promo_match:
            return f"{promo_match.group(1)}{promo_match.group(2)}".upper()
        
        # Check for standalone promo numbers
        if re.match(r'^(SWSH|SM|XY|BW)\d+$', card_number, re.IGNORECASE):
            return card_number.upper()
        
        # For regular set numbers, extract just the number part
        number_match = re.search(r'(\d+)', card_number)
        if number_match:
            return number_match.group(1)
        
        return card_number
    
    def _find_best_match(self, cards: List[Dict], target_name: str, target_set: str, target_number: str = None) -> Optional[Dict]:
        """Find the best matching card from search results"""
        if not cards:
            return None
        
        # Score each card
        scored_cards = []
        target_name_lower = target_name.lower()
        target_set_lower = target_set.lower()
        
        for card in cards:
            score = 0
            card_name = card.get('name', '').lower()
            card_set = card.get('set', {}).get('name', '').lower()
            card_number = card.get('number', '').lower()
            
            # Name matching (highest weight)
            if card_name == target_name_lower:
                score += 100
            elif target_name_lower in card_name or card_name in target_name_lower:
                score += 50
            
            # Set matching
            if card_set == target_set_lower:
                score += 50
            elif 'promo' in target_set_lower and 'promo' in card_set:
                score += 30
            elif target_set_lower in card_set or card_set in target_set_lower:
                score += 20
            
            # Number matching (very high weight for exact matches)
            if target_number:
                clean_target_number = self._clean_card_number(target_number).lower()
                if card_number == clean_target_number:
                    score += 80
                elif clean_target_number in card_number:
                    score += 40
            
            # Prefer cards with TCGPlayer data
            if card.get('tcgplayer', {}).get('url'):
                score += 10
            
            # Prefer cards with prices
            if card.get('tcgplayer', {}).get('prices'):
                score += 10
            
            scored_cards.append((score, card))
        
        # Sort by score and return best match
        scored_cards.sort(key=lambda x: x[0], reverse=True)
        
        if scored_cards and scored_cards[0][0] > 0:
            best_score, best_card = scored_cards[0]
            logger.debug(f"      Best match score: {best_score} for {best_card.get('name')} - {best_card.get('set', {}).get('name')}")
            return best_card
        
        return None
    
    def _extract_near_mint_price(self, card: Dict[str, Any], 
                                unique_characteristics: List[str] = None,
                                language: str = 'English') -> Tuple[Optional[float], Optional[str]]:
        """Extract NEAR MINT price from Pokemon TCG data based on card characteristics"""
        tcgplayer = card.get('tcgplayer', {})
        if not tcgplayer:
            return None, None
        
        prices = tcgplayer.get('prices', {})
        if not prices:
            return None, None
        
        # Determine price categories to check based on characteristics
        priority_categories = self._determine_price_categories(
            unique_characteristics, language, list(prices.keys()), 
            card.get('set', {}).get('name')
        )
        
        # Log only essential info
        if unique_characteristics:
            logger.info(f"      Edition: {', '.join(unique_characteristics)}")
        
        # Try to find a NEAR MINT price using the priority order
        for price_key in priority_categories:
            if price_key in prices:
                price_data = prices[price_key]
                if isinstance(price_data, dict):
                    # Pokemon TCG API uses 'market' for Near Mint market price
                    for price_field in ['market', 'mid']:  # Only Near Mint prices
                        if price_field in price_data:
                            price_value = price_data.get(price_field)
                            if price_value and float(price_value) > 0:
                                logger.info(f"      Using {price_key} Near Mint price: ${price_value}")
                                return float(price_value), price_key
        
        # Final fallback: Use ANY available Near Mint price (but warn about it)
        for price_category, price_data in prices.items():
            if isinstance(price_data, dict):
                for price_field in ['market', 'mid']:
                    if price_field in price_data:
                        price_value = price_data.get(price_field)
                        if price_value and float(price_value) > 0:
                            logger.warning(f"      ⚠️ No matching category - using {price_category} Near Mint: ${price_value}")
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
    
    def _extract_finish(self, card: Dict[str, Any], price_category: str) -> str:
        """Extract finish information from card data"""
        # [Keep the existing _extract_finish method unchanged]
        # ... (same as before)
    
    def _extract_features(self, card: Dict[str, Any], price_category: str) -> List[str]:
        """Extract special features/characteristics from card data"""
        # [Keep the existing _extract_features method unchanged]
        # ... (same as before)
    
    def _format_card_data(self, card: Dict[str, Any], market_price: float, 
                         price_category: str) -> Dict[str, Any]:
        """Format Pokemon card data with enhanced fields"""
        # Get the direct TCGPlayer URL from the API response
        tcgplayer_data = card.get('tcgplayer', {})
        tcgplayer_url = tcgplayer_data.get('url', '')
        
        # Validate the URL is a product URL, not a search URL
        if tcgplayer_url and '/product/' not in tcgplayer_url:
            logger.warning(f"      ⚠️ TCGPlayer URL appears to be a search page, not a product page")
            # You might want to set this to empty to trigger fallback
            # tcgplayer_url = ''
        
        # Extract finish and features from API data
        finish = self._extract_finish(card, price_category)
        features = self._extract_features(card, price_category)
        
        # Log what we found
        logger.info(f"      📊 Card: {card.get('name')} - {card.get('set', {}).get('name')} #{card.get('number')}")
        logger.info(f"      🔗 TCGPlayer URL: {tcgplayer_url if tcgplayer_url else 'Not found'}")
        
        # Get trainer/ability information if available
        abilities = card.get('abilities', [])
        ability_names = [ability.get('name', '') for ability in abilities] if abilities else []
        
        # Get attack information
        attacks = card.get('attacks', [])
        attack_names = [attack.get('name', '') for attack in attacks] if attacks else []
        
        # Get evolution information
        evolves_from = card.get('evolvesFrom', '')
        evolves_to = [evo for evo in card.get('evolvesTo', [])] if card.get('evolvesTo') else []
        
        return {
            'api_price': market_price,
            'price_source': f'Pokemon TCG API ({price_category}) - Near Mint',
            'price_category': price_category,
            'pokemon_tcg_id': card.get('id'),
            'hp': str(card.get('hp', '')),
            'types': card.get('types', []),
            'subtypes': card.get('subtypes', []),
            'supertype': card.get('supertype'),
            'artist': card.get('artist'),
            'rarity_confirmed': card.get('rarity'),
            'set_confirmed': card.get('set', {}).get('name'),
            'set_series': card.get('set', {}).get('series'),
            'set_total': card.get('set', {}).get('total'),
            'number_confirmed': card.get('number'),
            'release_date': card.get('set', {}).get('releaseDate'),
            'retreat_cost': card.get('retreatCost', []),
            'converted_retreat_cost': card.get('convertedRetreatCost'),
            'weaknesses': card.get('weaknesses', []),
            'resistances': card.get('resistances', []),
            'abilities': ability_names,
            'attacks': attack_names,
            'evolves_from': evolves_from,
            'evolves_to': evolves_to,
            'regulation_mark': card.get('regulationMark'),
            'finish_api': finish,
            'features_api': features,
            'data_source': 'Pokemon TCG API',
            'tcgplayer_url': tcgplayer_url,
            'tcgplayer_link': tcgplayer_url
        }