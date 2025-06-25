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
                        
                        # Select appropriate NEAR MINT price
                        # Scryfall prices are for Near Mint condition by default
                        if is_foil and 'usd_foil' in prices:
                            usd_price = float(prices.get('usd_foil', 0) or 0)
                            logger.info(f"      Using Near Mint foil price: ${usd_price}")
                        else:
                            usd_price = float(prices.get('usd', 0) or 0)
                            logger.info(f"      Using Near Mint regular price: ${usd_price}")
                        
                        if usd_price > 0:
                            return self._format_card_data(card, usd_price, is_foil)
                
                return None
                
        except Exception as e:
            logger.error(f"Scryfall API error: {e}")
            return None
    
    def _extract_finish(self, card: Dict[str, Any], is_foil: bool) -> str:
        """Extract finish information from MTG card data - FIXED VERSION"""
        
        # 1. Check card finishes array
        finishes = card.get('finishes', [])
        
        # 2. Check frame effects for special treatments
        frame_effects = card.get('frame_effects', [])
        
        # 3. Check if it's a special promo or treatment
        promo_types = card.get('promo_types', []) if card.get('promo') else []
        
        # 4. Check card layout for special types
        layout = card.get('layout', '')
        
        # 5. Check border color for special editions
        border_color = card.get('border_color', '')
        
        # 6. Check set information for special treatments
        set_name = card.get('set_name', '').lower()
        set_type = card.get('set_type', '')
        
        # 7. Build finish string based on all factors
        finish_parts = []
        
        # Special frame treatments (highest priority)
        frame_treatments = {
            # Standard treatments
            'showcase': 'Showcase',
            'extendedart': 'Extended Art',
            'borderless': 'Borderless',
            'fullart': 'Full Art',
            'textless': 'Textless',
            'inverted': 'Inverted',
            'etched': 'Etched',
            
            # Special frame types
            'fuse': 'Fuse',
            'companion': 'Companion',
            'nyxtouched': 'Nyxtouched',
            'miracle': 'Miracle',
            'lesson': 'Lesson',
            'snow': 'Snow',
            'legendary': 'Legendary',
            'devoid': 'Devoid',
            'tombstone': 'Tombstone',
            'colorshifted': 'Colorshifted',
            
            # Double-faced cards
            'sunmoondfc': 'Double-Faced',
            'mooneldrazidfc': 'Double-Faced',
            'originpwdfc': 'Double-Faced',
            'waxingandwaningmoondfc': 'Double-Faced',
            'convertdfc': 'Double-Faced',
            
            # Newer treatments
            'shatteredglass': 'Shattered Glass',
            'spaceic': 'Spaceic',
            'upsidedowndfc': 'Upside Down',
        }
        
        # Check for special frame treatments
        for effect in frame_effects:
            if effect in frame_treatments:
                finish_parts.append(frame_treatments[effect])
                break  # Usually only one major treatment
        
        # Check for special set-based foil treatments
        special_foil_treatments = {
            # Set-specific foils
            'unfinity': 'Galaxy Foil',
            'wilds of eldraine': 'Confetti Foil',
            'march of the machine': 'Halo Foil',
            'phyrexia: all will be one': 'Oil Slick',
            'the brothers\' war': 'Double Rainbow',
            
            # Product-specific foils
            'warhammer 40,000': 'Surge Foil',
            'doctor who': 'Surge Foil',
            'lord of the rings': 'Surge Foil',
            'fallout': 'Surge Foil',
            'assassin\'s creed': 'Surge Foil',
            'final fantasy': 'Surge Foil',
            
            # Special series
            'secret lair': 'Secret Lair',
            'from the vault': 'From the Vault',
            'masterpiece': 'Masterpiece',
            'mystical archive': 'Mystical Archive',
            'secret lair drop': 'Secret Lair',
        }
        
        # Check if this card has special foil treatment based on set
        foil_treatment = ''
        for set_pattern, treatment in special_foil_treatments.items():
            if set_pattern in set_name:
                foil_treatment = treatment
                break
        
        # Special finishes from the finishes array
        if 'etched' in finishes:
            if 'Etched' not in finish_parts:
                finish_parts.append('Etched')
        
        # Foil handling - now with special treatments
        if is_foil or 'foil' in finishes:
            # Check for special foil types first
            if foil_treatment:
                # Some treatments are standalone
                if foil_treatment in ['Galaxy Foil', 'Oil Slick', 'Surge Foil', 'Halo Foil', 
                                       'Confetti Foil', 'Double Rainbow']:
                    finish_parts.append(foil_treatment)
                elif foil_treatment == 'From the Vault':
                    finish_parts.append('From the Vault Foil')
                else:
                    # Add treatment if not already present
                    if foil_treatment not in finish_parts:
                        finish_parts.append(foil_treatment)
                    finish_parts.append('Foil')
            
            # Check for textured foil
            elif 'textured' in finishes or any('textured' in effect for effect in frame_effects):
                finish_parts.append('Textured Foil')
            
            # Check for etched foil combination
            elif 'etched' in finishes and 'foil' in finishes:
                # Both etched and foil
                if 'Etched' in finish_parts:
                    finish_parts.append('Foil')
                else:
                    finish_parts.append('Etched Foil')
            
            # Regular foil - but check for special foil types from promos
            elif promo_types:
                # Promo foils often have special designations
                promo_foil_types = {
                    'prerelease': 'Prerelease Foil',
                    'datestamped': 'Date Stamped Foil',
                    'stamped': 'Stamped Foil',
                    'setpromo': 'Set Promo Foil',
                    'buyabox': 'Buy-a-Box Foil',
                    'bundle': 'Bundle Foil',
                    'fnm': 'FNM Foil',
                    'judgegift': 'Judge Foil',
                    'arenaleague': 'Arena League Foil',
                    'gameday': 'Game Day Foil',
                    'release': 'Release Foil',
                    'convention': 'Convention Foil',
                    'tourney': 'Tournament Foil',
                    'instore': 'Store Championship Foil',
                    'openhouse': 'Open House Foil',
                    'planeswalkerstamped': 'Planeswalker Stamped Foil',
                    'wpnstamped': 'WPN Foil',
                    'playpromo': 'Play Promo Foil',
                }
                
                foil_added = False
                for promo in promo_types:
                    if promo in promo_foil_types:
                        finish_parts.append(promo_foil_types[promo])
                        foil_added = True
                        break
                
                if not foil_added and not foil_treatment:
                    finish_parts.append('Foil')
            else:
                # Standard foil (if no special treatment found)
                if not foil_treatment:
                    finish_parts.append('Foil')
        
        # Special set types that affect finish
        special_set_finishes = {
            'masterpiece': 'Masterpiece',
            'from_the_vault': 'From the Vault',
            'spellbook': 'Spellbook',
            'signature_spellbook': 'Signature Spellbook',
            'secret_lair': 'Secret Lair',
            'box': 'Box Topper',
            'memorabilia': 'Memorabilia',
            'masters': 'Masters',
            'duel_deck': 'Duel Deck',
            'commander': 'Commander',
            'planechase': 'Planechase',
            'archenemy': 'Archenemy',
            'vanguard': 'Vanguard',
            'funny': 'Un-set',
            'treasure_chest': 'Treasure Chest',
            'promo': 'Promo',
        }
        
        if set_type in special_set_finishes and special_set_finishes[set_type] not in finish_parts:
            finish_parts.append(special_set_finishes[set_type])
        
        # Special printings and variants
        if card.get('variation', False):
            finish_parts.append('Variant')
        
        if card.get('oversized', False):
            finish_parts.append('Oversized')
        
        # Serialized cards (check collector number)
        collector_number = card.get('collector_number', '')
        if '/' in collector_number and any(serial in collector_number for serial in ['999', '500', '250', '100']):
            finish_parts.append('Serialized')
        
        # Special treatments from card name
        card_name_lower = card.get('name', '').lower()
        if 'retro' in card_name_lower or 'old border' in card_name_lower:
            finish_parts.append('Retro Frame')
        
        # Rarity-based special finishes
        rarity = card.get('rarity', '')
        if rarity == 'mythic' and not any('Mythic' in part for part in finish_parts):
            # Some mythics have special finishes
            if 'showcase' in frame_effects or 'extendedart' in frame_effects:
                pass  # Already handled
            elif set_type in ['masters', 'core', 'expansion'] and is_foil:
                finish_parts.append('Mythic')
        
        # Special card treatments
        special_treatments = {
            # Bonus sheets
            'mystical archive': 'Mystical Archive',
            'multiverse legends': 'Multiverse Legends',
            'retro artifacts': 'Retro Artifacts',
            'enchanting tales': 'Enchanting Tales',
            'tales of middle-earth': 'Tales of Middle-earth',
            
            # Special frames
            'neon': 'Neon Ink',
            'schematic': 'Schematic',
            'blueprint': 'Blueprint',
            'stained glass': 'Stained Glass',
            'comic book': 'Comic Book',
            'anime': 'Anime',
            
            # Step treatments
            'step-and-compleat': 'Step-and-Compleat',
            'phyrexian': 'Phyrexian',
        }
        
        for pattern, treatment in special_treatments.items():
            if pattern in set_name or pattern in card_name_lower:
                if treatment not in finish_parts:
                    finish_parts.append(treatment)
        
        # Border colors (special editions)
        if border_color == 'gold':
            finish_parts.append('Gold Border')
        elif border_color == 'silver':
            finish_parts.append('Silver Border')
        
        # Special card types from type_line
        type_line = card.get('type_line', '').lower()
        if 'planeswalker' in type_line and is_foil and not any('Planeswalker' in part for part in finish_parts):
            # Special planeswalker printings
            if 'borderless' in frame_effects:
                pass  # Already handled as "Borderless"
            elif any(promo in promo_types for promo in ['stamped', 'prerelease']):
                pass  # Already handled
        
        # Combine finish parts intelligently
        if len(finish_parts) == 0:
            # CHANGED: Always return a finish - default to Non-Foil for regular cards
            return 'Non-Foil'
        elif len(finish_parts) == 1:
            return finish_parts[0]
        else:
            # Special combinations and priority ordering
            
            # Serialized takes highest priority
            if 'Serialized' in finish_parts:
                # Serialized + Double Rainbow (Brothers' War)
                if 'Double Rainbow' in finish_parts:
                    return 'Serialized Double Rainbow'
                else:
                    return 'Serialized'
            
            # Special foil treatments
            special_foils = ['Galaxy Foil', 'Oil Slick', 'Surge Foil', 'Halo Foil', 
                             'Confetti Foil', 'Double Rainbow', 'Step-and-Compleat']
            for special in special_foils:
                if special in finish_parts:
                    # These are complete treatments on their own
                    if 'Textured' in finish_parts and special == 'Oil Slick':
                        return 'Oil Slick Raised Foil'
                    return special
            
            # Frame treatments with foil
            if 'Showcase' in finish_parts and 'Foil' in finish_parts:
                return 'Showcase Foil'
            elif 'Extended Art' in finish_parts and 'Foil' in finish_parts:
                return 'Extended Art Foil'
            elif 'Borderless' in finish_parts and 'Foil' in finish_parts:
                return 'Borderless Foil'
            elif 'Full Art' in finish_parts and 'Foil' in finish_parts:
                return 'Full Art Foil'
            elif 'Etched' in finish_parts and 'Foil' in finish_parts:
                return 'Etched Foil'
            elif 'Textured Foil' in finish_parts:
                return 'Textured Foil'
            
            # Special sets/series
            special_priority = [
                'Masterpiece', 'Secret Lair', 'From the Vault',
                'Mystical Archive', 'Multiverse Legends',
                'Neon Ink', 'Phyrexian', 'Schematic'
            ]
            
            for special in special_priority:
                if special in finish_parts:
                    # Add foil designation if applicable
                    if any(f in finish_parts for f in ['Foil', 'Foil-Etched']):
                        return f'{special} Foil'
                    return special
            
            # Return the most specific/important finish
            priority_order = [
                'Showcase Foil', 'Extended Art Foil', 'Borderless Foil',
                'Showcase', 'Extended Art', 'Borderless', 'Full Art',
                'Etched Foil', 'Etched', 'Textured Foil',
                'Prerelease Foil', 'Judge Foil', 'Buy-a-Box Foil',
                'From the Vault Foil', 'Spellbook',
                'Foil', 'Mythic', 'Gold Border', 'Silver Border',
                'Variant', 'Promo'
            ]
            
            for priority_finish in priority_order:
                if priority_finish in finish_parts:
                    return priority_finish
            
            # Fallback to first finish
            return finish_parts[0]
    
    def _extract_features(self, card: Dict[str, Any]) -> List[str]:
        """Extract special features/characteristics from MTG card data - FIXED VERSION"""
        features = []
        
        # Frame effects - these are characteristics, not set names
        frame_effects = card.get('frame_effects', [])
        effect_mapping = {
            'showcase': 'Showcase',
            'extendedart': 'Extended Art',
            'borderless': 'Borderless',
            'fullart': 'Full Art',
            'textless': 'Textless',
            'inverted': 'Inverted',
            'companion': 'Companion',
            'etched': 'Etched',
            'shatteredglass': 'Shattered Glass',
            'convertdfc': 'Transform',
            'fandfc': 'Modal Double-Faced',
            'upsidedowndfc': 'Upside Down',
            'lesson': 'Lesson',
            'miracle': 'Miracle',
            'nyxtouched': 'Enchantment Creature',
            'draft': 'Draft Card',
            'devoid': 'Devoid',
            'tombstone': 'Flashback',
            'colorshifted': 'Colorshifted',
            'sunmoondfc': 'Daybound/Nightbound',
            'mooneldrazidfc': 'Meld',
            'originpwdfc': 'Origin',
            'waxingandwaningmoondfc': 'Disturb',
            'spaceic': 'Space-ic',
        }
        
        for effect in frame_effects:
            if effect in effect_mapping:
                features.append(effect_mapping[effect])
        
        # Promo information
        if card.get('promo'):
            promo_types = card.get('promo_types', [])
            promo_mapping = {
                'prerelease': 'Prerelease',
                'stamped': 'Stamped',
                'datestamped': 'Date Stamped',
                'buyabox': 'Buy-a-Box Promo',
                'bundle': 'Bundle Promo',
                'judgegift': 'Judge Gift',
                'fnm': 'FNM Promo',
                'gameday': 'Game Day Promo',
                'release': 'Release Promo',
                'convention': 'Convention Promo',
                'instore': 'Store Championship',
                'league': 'League Promo',
                'playerrewards': 'Player Rewards',
                'gateway': 'Gateway Promo',
                'wizardsplay': 'Wizards Play Network',
                'openhouse': 'Open House Promo',
                'tourney': 'Tournament Promo',
                'nationalsqualifier': 'Nationals Qualifier',
                'championshipqualifier': 'Championship Qualifier',
                'premiereshop': 'Premiere Shop',
                'grandprix': 'Grand Prix Promo',
                'protour': 'Pro Tour Promo',
                'worlds': 'Worlds Promo',
                'wpnstamped': 'WPN Promo',
                'playpromo': 'Play Promo',
                'planeswalkerstamped': 'Planeswalker Stamped',
                'setpromo': 'Set Promo',
                'promopack': 'Promo Pack',
                'themepack': 'Theme Booster',
                'brawldeck': 'Brawl Deck',
                'commanderparty': 'Commander Party',
            }
            
            for promo in promo_types:
                if promo in promo_mapping:
                    features.append(promo_mapping[promo])
            
            # If promo but no specific type
            if not promo_types and 'Promo' not in features:
                features.append('Promo')
        
        # REMOVED: Masterpiece series and special set names
        # These belong in the Set field, not Features
        
        set_name = card.get('set_name', '').lower()
        set_type = card.get('set_type', '')
        
        # Only add set TYPE if it's a characteristic, not a set name
        if set_type == 'funny':
            features.append('Un-set')
        
        # Frame information
        frame = card.get('frame', '')
        frame_features = {
            '1993': 'Alpha Frame',
            '1997': 'Classic Frame',
            '2003': 'Modern Frame',
            '2015': 'M15 Frame',
            'future': 'Future Frame',
            'timeshifted': 'Timeshifted Frame',
        }
        
        if frame in frame_features:
            features.append(frame_features[frame])
        
        # Border type - these are characteristics
        border = card.get('border_color', '')
        if border == 'gold':
            features.append('Gold Border')
        elif border == 'silver':
            features.append('Silver Border')
        elif border == 'white':
            features.append('White Border')
        
        # Special printings
        keywords = card.get('keywords', [])
        special_keywords = {
            'partner': 'Partner',
            'companion': 'Companion',
            'mutate': 'Mutate',
            'adventure': 'Adventure',
            'aftermath': 'Aftermath',
            'escape': 'Escape',
            'foretell': 'Foretell',
            'modal double-faced': 'Modal Double-Faced',
            'transform': 'Transform',
            'meld': 'Meld',
            'flip': 'Flip',
            'split': 'Split',
            'fuse': 'Fuse',
            'aftermath': 'Aftermath',
            'prototype': 'Prototype',
            'battle': 'Battle',
            'case': 'Case',
            'class': 'Class',
            'room': 'Room',
            'saga': 'Saga',
            'planeswalker': 'Planeswalker',
        }
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in special_keywords:
                features.append(special_keywords[keyword_lower])
        
        # Card layout special types
        layout = card.get('layout', '')
        layout_features = {
            'split': 'Split Card',
            'flip': 'Flip Card',
            'transform': 'Double-Faced Card',
            'modal_dfc': 'Modal Double-Faced Card',
            'meld': 'Meld Card',
            'leveler': 'Leveler',
            'class': 'Class Card',
            'saga': 'Saga',
            'adventure': 'Adventure Card',
            'mutate': 'Mutate Card',
            'prototype': 'Prototype Card',
            'battle': 'Battle Card',
            'case': 'Case Card',
            'room': 'Room Card',
            'planar': 'Planechase Card',
            'scheme': 'Archenemy Card',
            'vanguard': 'Vanguard Card',
            'token': 'Token',
            'emblem': 'Emblem',
            'art_series': 'Art Series',
            'reversible_card': 'Reversible Card',
        }
        
        if layout in layout_features:
            features.append(layout_features[layout])
        
        # Oversized cards
        if card.get('oversized'):
            features.append('Oversized')
        
        # Reserved list
        if card.get('reserved'):
            features.append('Reserved List')
        
        # Full art lands
        if card.get('full_art'):
            features.append('Full Art Land')
        
        # Textless
        if card.get('textless'):
            features.append('Textless')
        
        # Story spotlight
        if card.get('story_spotlight'):
            features.append('Story Spotlight')
        
        # Special card variations
        if card.get('variation'):
            features.append('Variant')
        
        # Unique/Special printings
        collector_number = card.get('collector_number', '')
        
        # Numbered cards (serialized)
        if '/' in collector_number and any(num in collector_number for num in ['999', '500', '250', '100', '50']):
            features.append('Numbered')
        
        # Special numbering schemes
        if collector_number:
            if collector_number.endswith('★'):
                features.append('Star Number')
            elif collector_number.endswith('†'):
                features.append('Dagger Number')
            elif any(letter in collector_number for letter in ['a', 'b', 'c', 'd', 'e']):
                features.append('Alternate Art')
            elif collector_number.startswith('F'):
                features.append('Foil-Only')
        
        # Special mechanics from oracle text
        oracle_text = card.get('oracle_text', '').lower()
        special_mechanics = {
            'draft matters': 'Draft Matters',
            'conspiracy': 'Conspiracy',
            'monarch': 'Monarch',
            'city\'s blessing': 'Ascend',
            'commander': 'Commander',
            'dungeon': 'Dungeon',
            'daybound': 'Daybound/Nightbound',
            'disturb': 'Disturb',
            'blood': 'Blood Token',
            'treasure': 'Treasure',
            'clue': 'Investigate',
            'food': 'Food Token',
            'role': 'Role Token',
            'sticker': 'Sticker',
            'attraction': 'Attraction',
            'contraption': 'Contraption',
            'energy': 'Energy',
            'experience': 'Experience Counter',
            'poison': 'Poison',
            'proliferate': 'Proliferate',
            'infect': 'Infect',
            'toxic': 'Toxic',
            'corrupted': 'Corrupted',
            'compleated': 'Compleated',
        }
        
        for mechanic, feature in special_mechanics.items():
            if mechanic in oracle_text and feature not in features:
                features.append(feature)
        
        # Arena/Digital only
        if card.get('digital'):
            features.append('Digital Only')
        
        if 'arena' in card.get('games', []) and len(card.get('games', [])) == 1:
            features.append('Arena Exclusive')
        
        # Special artist variations
        artist = card.get('artist', '').lower()
        if 'dan frazier' in artist and 'mox' in card.get('name', '').lower():
            features.append('Original Art')
        
        # Un-set specific
        if set_type == 'funny':
            # Check for specific Un-set mechanics
            if 'acorn' in card.get('security_stamp', ''):
                features.append('Acorn Card')
            elif 'oval' in card.get('security_stamp', ''):
                features.append('Eternal Legal')
        
        # Remove duplicates while preserving order
        seen = set()
        unique_features = []
        for feature in features:
            if feature not in seen:
                seen.add(feature)
                unique_features.append(feature)
        
        return unique_features
    
    def _format_card_data(self, card: Dict[str, Any], market_price: float, is_foil: bool) -> Dict[str, Any]:
        """Format MTG card data with enhanced fields"""
        # Scryfall provides purchase URLs
        purchase_urls = card.get('purchase_uris', {})
        tcgplayer_url = purchase_urls.get('tcgplayer', '')
        
        # Extract finish and features from API data
        finish = self._extract_finish(card, is_foil)
        features = self._extract_features(card)
        
        # Log what we're getting
        logger.info(f"   📊 Scryfall API - TCGPlayer data:")
        logger.info(f"      - Purchase URIs: {purchase_urls}")
        logger.info(f"      - TCGPlayer URL: {tcgplayer_url}")
        
        # Get game mechanics
        keywords = card.get('keywords', [])
        
        # Color information
        colors = card.get('colors', [])
        color_identity = card.get('color_identity', [])
        
        return {
            'api_price': market_price,
            'price_source': 'Scryfall API - Near Mint',  # Added Near Mint
            'scryfall_id': card.get('id'),
            'oracle_id': card.get('oracle_id'),
            'multiverse_ids': card.get('multiverse_ids', []),
            'tcgplayer_id': card.get('tcgplayer_id'),
            'cardmarket_id': card.get('cardmarket_id'),
            'oracle_text': card.get('oracle_text', ''),
            'mana_cost': card.get('mana_cost', ''),
            'cmc': card.get('cmc', 0),
            'type_line': card.get('type_line', ''),
            'colors': colors,
            'color_identity': color_identity,
            'keywords': keywords,
            'power': card.get('power'),  # ADDED - for creatures
            'toughness': card.get('toughness'),  # ADDED - for creatures
            'loyalty': card.get('loyalty'),  # For planeswalkers
            'artist': card.get('artist'),
            'rarity_confirmed': card.get('rarity'),
            'set_confirmed': card.get('set_name'),
            'set_code': card.get('set'),
            'collector_number': card.get('collector_number'),
            'release_date': card.get('released_at'),  # IMPORTANT - this needs to be passed through
            'reprint': card.get('reprint', False),
            'frame': card.get('frame'),
            'full_art': card.get('full_art', False),
            'textless': card.get('textless', False),
            'story_spotlight': card.get('story_spotlight', False),
            'oversized': card.get('oversized', False),  # ADDED - for card size detection
            'finish_api': finish,  # From API data
            'features_api': features,  # From API data
            'edhrec_rank': card.get('edhrec_rank'),
            'penny_rank': card.get('penny_rank'),
            'flavor_text': card.get('flavor_text'),
            'legalities': card.get('legalities', {}),
            'games': card.get('games', []),
            'data_source': 'Scryfall API',
            'tcgplayer_url': tcgplayer_url,  # Direct URL from API
            'tcgplayer_link': tcgplayer_url  # Also set as tcgplayer_link for consistency
        }