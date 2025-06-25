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
                        market_price, price_category = self._extract_near_mint_price(
                            card, unique_characteristics, language
                        )
                        if market_price is not None:
                            return self._format_card_data(card, market_price, price_category)
                
                return None
                
        except Exception as e:
            logger.error(f"Pokemon TCG API error: {e}")
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
        # Note: Pokemon TCG API typically includes condition in the price field names
        # We prioritize Near Mint prices (market price is usually Near Mint by default)
        for price_key in priority_categories:
            if price_key in prices:
                price_data = prices[price_key]
                if isinstance(price_data, dict):
                    # Pokemon TCG API uses 'market' for Near Mint market price
                    # 'mid' is also typically Near Mint
                    # We avoid 'low' as it might be for worse conditions
                    for price_field in ['market', 'mid']:  # Removed 'low' - only Near Mint
                        if price_field in price_data:
                            price_value = price_data.get(price_field)
                            if price_value and float(price_value) > 0:
                                logger.info(f"      Using {price_key} Near Mint price: ${price_value}")
                                return float(price_value), price_key
        
        # Final fallback: Use ANY available Near Mint price (but warn about it)
        for price_category, price_data in prices.items():
            if isinstance(price_data, dict):
                # Only use market or mid prices (Near Mint)
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
        """Extract finish information from card data - FIXED VERSION"""
        
        # 1. Check price category for finish information
        price_cat_lower = price_category.lower() if price_category else ''
        
        # Map price categories to finish types
        price_category_finishes = {
            'holofoil': 'Holo',
            'holo': 'Holo',
            'reverseholofoil': 'Reverse Holo',
            'reverse': 'Reverse Holo',
            '1steditionholofoil': 'Holo',
            'unlimitedholofoil': 'Holo',
            'normalholofoil': 'Holo',
            'foil': 'Foil',
            'nonholo': 'Non-Holo',  # CHANGED: Now returns Non-Holo
            'normal': 'Non-Holo',    # CHANGED: Now returns Non-Holo
        }
        
        # Extract finish from price category
        finish_from_price = ''
        for key, finish in price_category_finishes.items():
            if key in price_cat_lower:
                finish_from_price = finish
                break
        
        # 2. Check card rarity for holo information
        rarity = card.get('rarity', '').lower()
        rarity_finishes = {
            # Standard rarities
            'rare holo': 'Holo Rare',
            'holo rare': 'Holo Rare',
            'rare holo v': 'Holo V',
            'rare holo vmax': 'Holo VMAX',
            'rare holo vstar': 'Holo VSTAR',
            'rare holo ex': 'Holo EX',
            'rare holo gx': 'Holo GX',
            
            # Special rarities
            'rare secret': 'Secret Rare',
            'rare rainbow': 'Rainbow Rare',
            'rare ultra': 'Ultra Rare',
            'amazing rare': 'Amazing Rare',
            'rare shining': 'Shining',
            'rare shiny': 'Shiny',
            'shiny rare': 'Shiny Rare',
            'rare prism star': 'Prism Star',
            'rare ace': 'Ace Spec',
            'rare break': 'BREAK',
            'rare prime': 'Prime',
            
            # Newer special rarities
            'illustration rare': 'Illustration Rare',
            'special illustration rare': 'Special Illustration Rare',
            'character rare': 'Character Rare',
            'hyper rare': 'Hyper Rare',
            'radiant rare': 'Radiant',
            'rare radiant': 'Radiant',
        }
        
        finish_from_rarity = ''
        for key, finish in rarity_finishes.items():
            if key in rarity:
                finish_from_rarity = finish
                break
        
        # If we only found "holo" in rarity but not a specific type
        if not finish_from_rarity and 'holo' in rarity:
            if 'reverse' in rarity:
                finish_from_rarity = 'Reverse Holo'
            else:
                finish_from_rarity = 'Holo'
        
        # 3. Check for special card types from subtypes
        subtypes = card.get('subtypes', [])
        subtype_finishes = {
            # Modern Pokemon types
            'EX': 'EX',
            'GX': 'GX',
            'V': 'V',
            'VMAX': 'VMAX',
            'VSTAR': 'VSTAR',
            'ex': 'ex',  # Newer lowercase ex
            
            # Classic types
            'Prime': 'Prime',
            'BREAK': 'BREAK',
            'LV.X': 'LV.X',
            'LEGEND': 'LEGEND',
            'TAG TEAM': 'TAG TEAM',
            
            # Special types
            'Prism Star': 'Prism Star',
            'Radiant': 'Radiant',
            'Fusion Strike': 'Fusion Strike',
            'Single Strike': 'Single Strike',
            'Rapid Strike': 'Rapid Strike',
            
            # Tera types
            'Tera': 'Tera',
            'Stellar': 'Stellar Tera',
        }
        
        finish_from_subtype = ''
        for subtype in subtypes:
            if subtype in subtype_finishes:
                finish_from_subtype = subtype_finishes[subtype]
                # For V, VMAX, VSTAR, GX, EX - these are always holo
                if finish_from_subtype in ['V', 'VMAX', 'VSTAR', 'GX', 'EX', 'ex']:
                    # Combine with holo if not already specified
                    if not finish_from_price and not finish_from_rarity:
                        finish_from_subtype = f'Holo {finish_from_subtype}'
                break
        
        # 4. Check for special finishes in card name, set info, or number
        card_name = card.get('name', '').lower()
        set_name = card.get('set', {}).get('name', '').lower()
        card_number = card.get('number', '').upper()
        
        special_finishes = {
            # Art variants
            'full art': 'Full Art',
            'alternate art': 'Alternate Art',
            'alt art': 'Alternate Art',
            'character art': 'Character Art',
            'special art': 'Special Art',
            
            # Rarity types
            'secret': 'Secret Rare',
            'gold': 'Gold',
            'rainbow': 'Rainbow Rare',
            'shining': 'Shining',
            'shiny': 'Shiny',
            'crystal': 'Crystal',
            
            # Special sets/subsets
            'trainer gallery': 'Trainer Gallery',
            'galarian gallery': 'Galarian Gallery',
            'shiny vault': 'Shiny Vault',
            'hidden fates': 'Shiny Vault',
            'shining fates': 'Shiny Vault',
            'paldean fates': 'Shiny Rare',
            
            # Pokemon-specific
            'delta species': 'Delta Species',
            'character rare': 'Character Rare',
            'illustration rare': 'Illustration Rare',
            'special illustration': 'Special Illustration Rare',
            'classic collection': 'Classic Collection',
            
            # Newer treatments
            'radiant collection': 'Radiant Collection',
            'cosmic': 'Cosmos Holo',
            'cosmos': 'Cosmos Holo',
            'swirl': 'Swirl Holo',
            'confetti': 'Confetti Holo',
            'cracked ice': 'Cracked Ice Holo',
            'mirror': 'Mirror Holo',
            'etched': 'Etched',
        }
        
        finish_from_special = ''
        combined_text = f"{card_name} {set_name}"
        for key, finish in special_finishes.items():
            if key in combined_text:
                finish_from_special = finish
                break
        
        # Check card number patterns for special galleries
        if card_number:
            # Trainer Gallery cards (TG prefix)
            if card_number.startswith('TG'):
                finish_from_special = 'Trainer Gallery'
            # Galarian Gallery cards (GG prefix)
            elif card_number.startswith('GG'):
                finish_from_special = 'Galarian Gallery'
            # Shiny Vault cards (SV prefix)
            elif card_number.startswith('SV'):
                finish_from_special = 'Shiny Vault'
            # Radiant Collection (RC prefix)
            elif card_number.startswith('RC'):
                finish_from_special = 'Radiant Collection'
            # Black Star Promos
            elif 'PROMO' in card_number or card_number.startswith('PR'):
                if not finish_from_special:
                    finish_from_special = 'Promo'
        
        # 5. Check if it's a promo card
        if 'promo' in set_name or card.get('number', '').upper().startswith('PROMO'):
            # Promos are often holo but not always
            if not finish_from_price and not finish_from_rarity and not finish_from_subtype:
                # Check if the promo price category suggests holo
                if 'holo' in price_cat_lower or 'foil' in price_cat_lower:
                    finish_from_special = 'Holo Promo'
                elif not finish_from_special:
                    finish_from_special = 'Promo'
        
        # 6. Special era/set specific finishes
        era_specific_finishes = {
            # E-Card series
            'aquapolis': 'E-Reader',
            'skyridge': 'E-Reader',
            'expedition': 'E-Reader',
            
            # Special sets
            'celebrations': 'Classic Collection',
            'evolutions': 'Evolutions',
            'generations': 'Generations',
            'call of legends': 'Call of Legends',
            'dragon vault': 'Dragon Vault',
            'double crisis': 'Double Crisis',
            
            # Championship cards
            'world championship': 'World Championship',
            'championship': 'Championship',
        }
        
        for pattern, finish in era_specific_finishes.items():
            if pattern in set_name:
                if not finish_from_special:
                    finish_from_special = finish
                break
        
        # 7. Combine finishes intelligently
        # Priority order: special gallery/subset > subtype > special > rarity > price category
        finishes = []
        
        # Add gallery/subset finishes first (highest priority)
        if finish_from_special and finish_from_special in ['Trainer Gallery', 'Galarian Gallery', 
                                                            'Shiny Vault', 'Radiant Collection']:
            finishes.append(finish_from_special)
        
        # Add special finishes (Full Art, Alt Art, etc)
        elif finish_from_special and finish_from_special not in ['Promo']:
            finishes.append(finish_from_special)
        
        # Add subtype-based finish
        if finish_from_subtype and finish_from_subtype not in finishes:
            finishes.append(finish_from_subtype)
        
        # Add rarity-based finish if not redundant
        if finish_from_rarity and finish_from_rarity not in finishes:
            # Don't add "Holo" if we already have a more specific holo type
            if not (finish_from_rarity == 'Holo' and any('Holo' in f for f in finishes)):
                finishes.append(finish_from_rarity)
        
        # Add price-based finish if not redundant
        if finish_from_price and finish_from_price not in finishes:
            # Don't add generic "Holo" if we have specific holo type
            if not (finish_from_price in ['Holo', 'Reverse Holo'] and 
                    any(f in finishes for f in ['Holo V', 'Holo VMAX', 'Holo EX', 'Holo GX'])):
                finishes.append(finish_from_price)
        
        # Combine finishes
        if finishes:
            # Special handling for combinations
            if len(finishes) == 1:
                return finishes[0]
            else:
                # Gallery cards with specific types
                if any(gallery in finishes for gallery in ['Trainer Gallery', 'Galarian Gallery']):
                    gallery = next(g for g in ['Trainer Gallery', 'Galarian Gallery'] if g in finishes)
                    if any(v in finishes for v in ['V', 'VMAX', 'VSTAR', 'GX', 'EX']):
                        base_type = next(v for v in ['VSTAR', 'VMAX', 'V', 'GX', 'EX'] if v in finishes)
                        return f'{gallery} {base_type}'
                    else:
                        return gallery
                
                # Art variants with types
                elif 'Full Art' in finishes and any(v in finishes for v in ['V', 'VMAX', 'VSTAR', 'GX', 'EX']):
                    base_type = next(v for v in ['VSTAR', 'VMAX', 'V', 'GX', 'EX'] if v in finishes)
                    return f'Full Art {base_type}'
                elif 'Alternate Art' in finishes and any(v in finishes for v in ['V', 'VMAX', 'VSTAR']):
                    base_type = next(v for v in ['VSTAR', 'VMAX', 'V'] if v in finishes)
                    return f'Alternate Art {base_type}'
                
                # Special finishes take priority
                elif 'Rainbow Rare' in finishes:
                    return 'Rainbow Rare'
                elif 'Gold' in finishes:
                    return 'Gold'
                elif 'Secret Rare' in finishes:
                    return 'Secret Rare'
                elif 'Special Illustration Rare' in finishes:
                    return 'Special Illustration Rare'
                elif 'Illustration Rare' in finishes:
                    return 'Illustration Rare'
                elif 'Character Rare' in finishes:
                    return 'Character Rare'
                elif 'Radiant' in finishes:
                    return 'Radiant'
                elif 'Shiny Vault' in finishes:
                    return 'Shiny Vault'
                else:
                    # Return the most specific finish
                    return finishes[0]
        
        # 8. Final fallback - check if it's a basic holo based on other indicators
        if not finishes:
            # Check if it's a rare card that's likely to be holo
            if any(r in rarity for r in ['rare', 'ultra', 'secret', 'prism']):
                # Check if the price suggests it's a holo (holo versions typically cost more)
                tcgplayer = card.get('tcgplayer', {})
                prices = tcgplayer.get('prices', {})
                
                # If there are both normal and holofoil prices, and we're using holofoil price
                if 'holofoil' in prices and 'normal' in prices:
                    holo_price = prices.get('holofoil', {}).get('market', 0)
                    normal_price = prices.get('normal', {}).get('market', 0)
                    if holo_price > normal_price and 'holo' in price_cat_lower:
                        return 'Holo'
        
        # CHANGED: Always return a finish - default to Non-Holo for regular cards
        # This ensures eBay finish field is always populated
        if not finishes:
            return 'Non-Holo'
        
        # This should never be reached now, but just in case
        return 'Non-Holo'
    
    def _extract_features(self, card: Dict[str, Any], price_category: str) -> List[str]:
        """Extract special features/characteristics from card data - FIXED VERSION"""
        features = []
        
        # Extract from price category
        if price_category:
            price_cat_lower = price_category.lower()
            price_features = {
                '1stedition': '1st Edition',
                'firstedition': '1st Edition',
                'first': '1st Edition',
                'shadowless': 'Shadowless',
                'unlimited': 'Unlimited',
                # REMOVED: baseset2, legendary, evolutions - these are set names
            }
            
            for key, feature in price_features.items():
                if key in price_cat_lower:
                    # Don't add Unlimited if it's 1st Edition
                    if feature == 'Unlimited' and any('1st' in f for f in features):
                        continue
                    features.append(feature)
        
        # Check set information for special editions
        set_data = card.get('set', {})
        set_name = set_data.get('name', '').lower()
        set_id = set_data.get('id', '').lower()
        
        # Base Set variants - these are characteristics, not set names
        if 'base set' in set_name:
            # Only add the characteristic, not the set name
            if 'shadowless' in set_name:
                features.append('Shadowless')
            # Check if it's 1st edition base set
            if '1st' in price_cat_lower and 'base set' in set_name:
                features.append('1st Edition')
        
        # Special CHARACTERISTICS (not set names)
        special_characteristics = {
            # Promotional types
            'promo': 'Promo',
            'black star': 'Black Star Promo',
            'wizards': 'Wizards Promo',
            'nintendo': 'Nintendo Promo',
            'play!': 'Play! Promo',
            'league': 'League Promo',
            'championship': 'Championship',
            'world championship': 'World Championship',
            'trophy': 'Trophy Card',
            'winner': 'Tournament Winner',
            'staff': 'Staff',
            'prerelease': 'Prerelease',
            'stamped': 'Stamped',
            
            # Print variations
            'error': 'Error',
            'misprint': 'Misprint',
            'miscut': 'Miscut',
            'corrected': 'Corrected',
            'test': 'Test Card',
            'sample': 'Sample',
            
            # Special stamps/markings
            'winner': 'Winner Stamp',
            'participant': 'Participant Stamp',
            'regional': 'Regional Stamp',
            'worlds': 'Worlds Stamp',
            'champion': 'Champion Stamp',
        }
        
        # REMOVED: Set names like expedition, aquapolis, dragon vault, etc.
        # These belong in the Set field, not Features
        
        for key, feature in special_characteristics.items():
            if key in set_name or key in set_id:
                if feature not in features:
                    features.append(feature)
        
        # Check card number for special indicators
        card_number = card.get('number', '').upper()
        if card_number:
            # Only add if it's a special designation, not gallery names
            if 'PROMO' in card_number or card_number.startswith('PR'):
                if 'Promo' not in features:
                    features.append('Promo')
            elif card_number.startswith('W'):
                features.append('Wizards Promo')
            elif card_number.startswith('NP'):
                features.append('Nintendo Promo')
            elif '☆' in card_number:
                features.append('Star')
            # REMOVED: Gallery prefixes (TG, GG, SV, RC) - these are handled in finish
        
        # Check for special rarities that are characteristics
        rarity = card.get('rarity', '').lower()
        
        # Special card attributes from name
        card_name = card.get('name', '').lower()
        
        # Delta Species
        if 'δ' in card_name or 'delta' in card_name:
            features.append('Delta Species')
        
        # Dark/Light Pokemon
        if card_name.startswith('dark '):
            features.append('Dark')
        elif card_name.startswith('light '):
            features.append('Light')
        
        # Team variants
        team_prefixes = {
            'team rocket\'s': 'Team Rocket',
            'team aqua\'s': 'Team Aqua',
            'team magma\'s': 'Team Magma',
            'team plasma\'s': 'Team Plasma',
            'team flare\'s': 'Team Flare',
        }
        
        for prefix, team in team_prefixes.items():
            if card_name.startswith(prefix):
                features.append(team)
        
        # Owner's Pokemon
        if '\'s ' in card_name and not any(team in card_name for team in team_prefixes.keys()):
            # It's an owner's Pokemon (like Brock's Geodude)
            features.append('Owner\'s')
        
        # Battle Styles (these are characteristics)
        if 'Single Strike' in card_name or 'single strike' in str(card.get('abilities', [])):
            features.append('Single Strike')
        elif 'Rapid Strike' in card_name or 'rapid strike' in str(card.get('abilities', [])):
            features.append('Rapid Strike')
        elif 'Fusion Strike' in card_name or 'fusion strike' in str(card.get('abilities', [])):
            features.append('Fusion Strike')
        
        # Ancient/Future
        abilities = card.get('abilities', [])
        if abilities:
            ability_names = [a.get('name', '').lower() for a in abilities]
            if any('ancient' in name for name in ability_names):
                features.append('Ancient')
            elif any('future' in name for name in ability_names):
                features.append('Future')
        
        # Special printings and errors
        if 'error' in set_name or 'error' in card_name:
            features.append('Error')
        elif 'misprint' in set_name:
            features.append('Misprint')
        elif 'corrected' in set_name:
            features.append('Corrected')
        
        # Test cards
        if 'test' in set_name or 'sample' in card_name:
            features.append('Test Card')
        
        # Special edition markers from combined text
        combined_text = f"{card_name} {set_name} {rarity}"
        
        # Championship/tournament stamps
        if any(term in combined_text for term in ['winner', 'champion', 'tournament']):
            if 'winner' in combined_text and 'Winner Stamp' not in features:
                features.append('Winner Stamp')
            elif 'champion' in combined_text and 'Champion Stamp' not in features:
                features.append('Champion Stamp')
        
        # Language variants (only for non-English) - but this might be redundant with Language field
        # Commenting out since Language is already a separate field
        # language = card.get('set', {}).get('language', '')
        # if language and language.lower() != 'english':
        #     features.append(language.title())
        
        # Remove duplicates while preserving order
        seen = set()
        unique_features = []
        for feature in features:
            if feature not in seen:
                seen.add(feature)
                unique_features.append(feature)
        
        return unique_features
    
    def _format_card_data(self, card: Dict[str, Any], market_price: float, 
                         price_category: str) -> Dict[str, Any]:
        """Format Pokemon card data with enhanced fields"""
        # Get the direct TCGPlayer URL from the API response
        tcgplayer_data = card.get('tcgplayer', {})
        tcgplayer_url = tcgplayer_data.get('url', '')
        
        # Extract finish and features from API data
        finish = self._extract_finish(card, price_category)
        features = self._extract_features(card, price_category)
        
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
            'price_source': f'Pokemon TCG API ({price_category}) - Near Mint',  # Added Near Mint
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
            'finish_api': finish,  # From API data, not Ximilar
            'features_api': features,  # From API data, not Ximilar
            'data_source': 'Pokemon TCG API',
            'tcgplayer_url': tcgplayer_url,
            'tcgplayer_link': tcgplayer_url
        }