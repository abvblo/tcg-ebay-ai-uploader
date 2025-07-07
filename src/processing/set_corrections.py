"""Set data corrections for known misidentifications"""

from typing import Dict, Tuple, Optional
from ..utils.logger import logger

class SetCorrector:
    """Correct known set data issues from AI identification"""
    
    # Known set sizes - format: "Set Name": total_cards
    # Note: These are the regular set sizes. Secret rares will have numbers above these.
    KNOWN_SET_SIZES = {
        # Base Set Era (1999-2000)
        "Base Set": 102,
        "Jungle": 64,
        "Fossil": 62,
        "Base Set 2": 130,
        "Team Rocket": 83,
        "Gym Heroes": 132,
        "Gym Challenge": 132,
        
        # Neo Era (2000-2001)
        "Neo Genesis": 111,
        "Neo Discovery": 75,
        "Neo Revelation": 66,
        "Neo Destiny": 113,
        
        # Legendary Collection
        "Legendary Collection": 110,
        
        # e-Card Era (2002-2003)
        "Expedition Base Set": 165,
        "Aquapolis": 186,
        "Skyridge": 182,
        
        # EX Era (2003-2007)
        "EX Ruby & Sapphire": 109,
        "EX Sandstorm": 100,
        "EX Dragon": 100,
        "EX Team Magma vs Team Aqua": 97,
        "EX Hidden Legends": 102,
        "EX FireRed & LeafGreen": 116,
        "EX Team Rocket Returns": 111,
        "EX Deoxys": 108,
        "EX Emerald": 107,
        "EX Unseen Forces": 145,
        "EX Delta Species": 114,
        "EX Legend Maker": 93,
        "EX Holon Phantoms": 111,
        "EX Crystal Guardians": 100,
        "EX Dragon Frontiers": 101,
        "EX Power Keepers": 108,
        
        # Diamond & Pearl Era (2007-2009)
        "Diamond & Pearl": 130,
        "Mysterious Treasures": 124,
        "Secret Wonders": 132,
        "Great Encounters": 106,
        "Majestic Dawn": 100,
        "Legends Awakened": 146,
        "Stormfront": 106,
        
        # Platinum Era (2009-2010)
        "Platinum": 133,
        "Rising Rivals": 120,
        "Supreme Victors": 153,
        "Arceus": 99,
        
        # HeartGold & SoulSilver Era (2010-2011)
        "HeartGold & SoulSilver": 124,
        "Unleashed": 96,
        "Undaunted": 91,
        "Triumphant": 103,
        "Call of Legends": 106,
        
        # Black & White Era (2011-2013)
        "Black & White": 114,
        "Emerging Powers": 98,
        "Noble Victories": 101,
        "Next Destinies": 99,
        "Dark Explorers": 108,
        "Dragons Exalted": 124,
        "Dragon Vault": 20,
        "Boundaries Crossed": 149,
        "Plasma Storm": 135,
        "Plasma Freeze": 116,
        "Plasma Blast": 101,
        "Legendary Treasures": 113,
        
        # XY Series
        "XY": 146,
        "Flashfire": 106,
        "Furious Fists": 111,
        "Phantom Forces": 119,
        "Primal Clash": 160,
        "Double Crisis": 34,
        "Roaring Skies": 108,
        "Ancient Origins": 98,
        "BREAKthrough": 162,
        "BREAKpoint": 122,
        "Generations": 83,
        "Fates Collide": 124,
        "Steam Siege": 114,
        "Evolutions": 108,
        
        # Sun & Moon Series (2017-2019)
        "Sun & Moon": 149,
        "Guardians Rising": 145,
        "Burning Shadows": 147,
        "Shining Legends": 73,
        "Crimson Invasion": 111,
        "Ultra Prism": 156,
        "Forbidden Light": 131,
        "Celestial Storm": 168,
        "Dragon Majesty": 70,
        "Lost Thunder": 214,
        "Team Up": 181,
        "Detective Pikachu": 18,
        "Unbroken Bonds": 214,
        "Unified Minds": 236,
        "Hidden Fates": 68,
        "Cosmic Eclipse": 236,
        
        # Sword & Shield Series (2020-2023)
        "Sword & Shield": 202,
        "Rebel Clash": 192,
        "Darkness Ablaze": 189,
        "Champion's Path": 73,
        "Vivid Voltage": 185,
        "Shining Fates": 72,
        "Battle Styles": 163,
        "Chilling Reign": 198,
        "Evolving Skies": 203,
        "Celebrations": 25,
        "Fusion Strike": 264,
        "Brilliant Stars": 172,
        "Astral Radiance": 189,
        "Pokemon GO": 78,
        "Lost Origin": 196,
        "Silver Tempest": 195,
        "Crown Zenith": 159,
        
        # Scarlet & Violet Series (2023-Present)
        "Scarlet & Violet": 198,
        "Paldea Evolved": 193,
        "Obsidian Flames": 197,
        "151": 165,  # Special set
        "Paradox Rift": 182,
        "Paldean Fates": 91,  # Special set
        "Temporal Forces": 162,
        "Twilight Masquerade": 167,
        "Shrouded Fable": 64,  # Special set
        "Stellar Crown": 142,
        "Surging Sparks": 191,
        "Prismatic Evolutions": 176,  # Special set Jan 2025
        "Destined Rivals": 162,  # Feb 2025 release
        "Scarlet & Violet 151": 165,  # Alternative name for 151
        "Pokémon Card 151": 165,  # Another alternative name
        
        # Special Sets & Collections
        "Southern Islands": 18,
        "Pokemon Rumble": 16,
        "McDonald's Collection 2011": 12,
        "McDonald's Collection 2012": 12,
        "McDonald's Collection 2013": 12,
        "McDonald's Collection 2014": 12,
        "McDonald's Collection 2015": 12,
        "McDonald's Collection 2016": 12,
        "McDonald's Collection 2017": 12,
        "McDonald's Collection 2018": 12,
        "McDonald's Collection 2019": 12,
        "McDonald's Collection 2021": 25,
        "McDonald's Collection 2022": 15,
        "McDonald's Collection 2023": 15,
        "McDonald's Collection 2024": 15,
        "Pokémon TCG: Classic": 103,
        "Pokémon GO TCG": 78,
        "Trainer Gallery": 30,  # Various subset sizes
        "Radiant Collection": 25,  # Legendary Treasures subset
        "Shiny Vault": 94,  # Hidden Fates subset
        "Amazing Rare": 9,  # Vivid Voltage subset
        "Galarian Gallery": 30,  # Various subset sizes
        
        # Promo Sets
        "Black Star Promos": 101,  # Original series
        "DP Black Star Promos": 56,
        "HGSS Black Star Promos": 25,
        "BW Black Star Promos": 101,
        "XY Black Star Promos": 211,
        "SM Black Star Promos": 250,
        "SWSH Black Star Promos": 300,  # Approximate, still growing
        "SVP Black Star Promos": 150,  # Approximate, still growing
        
        # Scarlet & Violet Subsets/Collections
        "Illustration Rare Collection": 30,  # Various SV subsets
        "Special Illustration Rare": 50,  # Various SV subsets
        "Art Rare": 30,  # Various SV subsets
    }
    
    # Card-specific corrections - format: ("Card Name", "Set Name"): ("correct_number", "correct_total")
    SPECIFIC_CORRECTIONS = {
        # Add specific card corrections here as needed
        ("Wobbuffet", "XY"): ("RC11", "32"),  # BREAK card often misidentified
        # Common misidentifications from logs
        ("Venusaur", "Evolutions"): ("1", "108"),
        ("Terrakion", "Emerging Powers"): ("63", "98"),
        ("Palpitoad", "Boundaries Crossed"): ("35", "149"),
        ("Toxicroak", "Arceus"): ("11", "99"),
        ("Bewear", "Crimson Invasion"): ("56", "111"),
        ("Treecko", "Lost Thunder"): ("20", "214"),
        ("Tool Scrapper", "Rebel Clash"): ("208", "192"),
        # Promo corrections
        ("Arcanine", "XY Promos"): ("XY180", ""),
        ("Arcanine BREAK", "XY Promos"): ("XY180", ""),
        ("Dialga", "SWSH Promos"): ("SWSH135", ""),
        ("Rockruff", "SM Promos"): ("SM86", ""),
        ("Tornadus", "BW Promos"): ("BW81", ""),
        ("Landorus", "BW Promos"): ("BW79", ""),
        ("Celebi", "BW Promos"): ("BW50", ""),
        ("Snivy", "BW Promos"): ("BW01", ""),
        ("Tepig", "BW Promos"): ("BW02", ""),
        ("Oshawott", "BW Promos"): ("BW03", ""),
        ("Pikachu", "BW Promos"): ("BW54", ""),
        
        # Additional BW Promos
        ("Venusaur", "BW Promos"): ("BW28", ""),
        ("Charizard", "BW Promos"): ("BW54", ""),
        ("Blastoise", "BW Promos"): ("BW59", ""),
        ("Thundurus", "BW Promos"): ("BW80", ""),
        ("Reshiram", "BW Promos"): ("BW004", ""),
        ("Zekrom", "BW Promos"): ("BW005", ""),
        ("Kyurem", "BW Promos"): ("BW59", ""),
        
        # XY Promos
        ("Chespin", "XY Promos"): ("XY01", ""),
        ("Fennekin", "XY Promos"): ("XY02", ""),
        ("Froakie", "XY Promos"): ("XY03", ""),
        ("Xerneas", "XY Promos"): ("XY07", ""),
        ("Yveltal", "XY Promos"): ("XY08", ""),
        ("Garchomp", "XY Promos"): ("XY09", ""),
        ("Mewtwo", "XY Promos"): ("XY101", ""),
        ("Mew", "XY Promos"): ("XY110", ""),
        ("Pikachu", "XY Promos"): ("XY95", ""),
        ("Hoopa", "XY Promos"): ("XY71", ""),
        ("Volcanion", "XY Promos"): ("XY164", ""),
        
        # SM Promos
        ("Rowlet", "SM Promos"): ("SM01", ""),
        ("Litten", "SM Promos"): ("SM02", ""),
        ("Popplio", "SM Promos"): ("SM03", ""),
        ("Pikachu", "SM Promos"): ("SM04", ""),
        ("Solgaleo", "SM Promos"): ("SM16", ""),
        ("Lunala", "SM Promos"): ("SM17", ""),
        ("Lycanroc", "SM Promos"): ("SM14", ""),
        ("Zygarde", "SM Promos"): ("SM48", ""),
        ("Tapu Koko", "SM Promos"): ("SM30", ""),
        ("Mewtwo", "SM Promos"): ("SM77", ""),
        ("Umbreon", "SM Promos"): ("SM55", ""),
        
        # SWSH Promos
        ("Grookey", "SWSH Promos"): ("SWSH01", ""),
        ("Scorbunny", "SWSH Promos"): ("SWSH02", ""),
        ("Sobble", "SWSH Promos"): ("SWSH03", ""),
        ("Pikachu", "SWSH Promos"): ("SWSH020", ""),
        ("Zacian", "SWSH Promos"): ("SWSH018", ""),
        ("Zamazenta", "SWSH Promos"): ("SWSH019", ""),
        ("Eternatus", "SWSH Promos"): ("SWSH044", ""),
        ("Dragapult", "SWSH Promos"): ("SWSH096", ""),
        ("Toxtricity", "SWSH Promos"): ("SWSH017", ""),
        ("Eevee", "SWSH Promos"): ("SWSH095", ""),
        
        # McDonald's corrections
        ("Totodile", "McDonald's Collection"): ("5", "12"),
        ("Dwebble", "McDonald's Collection"): ("13", "25"),
        ("Pikachu", "McDonald's Collection 2021"): ("25", "25"),
        ("Charmander", "McDonald's Collection 2021"): ("9", "25"),
        ("Bulbasaur", "McDonald's Collection 2021"): ("1", "25"),
        ("Squirtle", "McDonald's Collection 2021"): ("15", "25"),
    }
    
    def correct_card_data(self, card_name: str, set_name: str, card_number: str) -> Tuple[str, Optional[str]]:
        """
        Correct card number and set total if needed
        
        Returns:
            Tuple of (corrected_number, reason_for_correction)
        """
        # First check for specific card corrections
        specific_key = (card_name, set_name)
        if specific_key in self.SPECIFIC_CORRECTIONS:
            correct_number, correct_total = self.SPECIFIC_CORRECTIONS[specific_key]
            if correct_total:
                corrected = f"{correct_number}/{correct_total}"
            else:
                corrected = correct_number
            logger.info(f"   🔧 Applied specific correction: {card_number} → {corrected}")
            return corrected, f"Specific correction for {card_name}"
        
        # Check if we need to correct the set total
        if '/' in card_number:
            parts = card_number.split('/')
            if len(parts) == 2:
                current_num = parts[0]
                current_total = parts[1]
                
                # Look for the set in our known sizes
                for known_set, correct_total in self.KNOWN_SET_SIZES.items():
                    if known_set.lower() in set_name.lower():
                        if str(current_total) != str(correct_total):
                            corrected = f"{current_num}/{correct_total}"
                            logger.info(f"   🔧 Corrected set size: {card_number} → {corrected}")
                            return corrected, f"Set size correction for {known_set}"
                        break
        
        # No correction needed
        return card_number, None
    
    def validate_card_number(self, card_name: str, set_name: str, card_number: str) -> bool:
        """
        Validate if a card number makes sense for the given set
        
        Returns:
            True if valid, False if suspicious
        """
        if '/' not in card_number:
            return True  # Can't validate without total
        
        parts = card_number.split('/')
        if len(parts) != 2:
            return True  # Unusual format, can't validate
        
        try:
            num = int(parts[0])
            total = int(parts[1])
            
            # Check if this could be a secret rare
            is_secret_rare = num > total
            
            if is_secret_rare:
                # Secret rares are valid - they exceed the set total
                # Common patterns: Full Arts, Rainbow Rares, Gold Cards, etc.
                # These typically appear 1-20 numbers above the set total
                if num > total + 50:
                    # Suspiciously high - might be misidentified
                    logger.warning(f"   ⚠️ Card number {num} is unusually high for set total {total}")
                    return False
                else:
                    # This is likely a valid secret rare
                    logger.debug(f"   ✨ Secret rare detected: {num}/{total}")
                    return True
            
            # For non-secret rares, check against known set sizes
            for known_set, correct_total in self.KNOWN_SET_SIZES.items():
                if known_set.lower() in set_name.lower():
                    if total != correct_total:
                        # The total doesn't match what we expect
                        logger.warning(f"   ⚠️ Set total {total} doesn't match known size {correct_total} for {known_set}")
                        # Still return True as it might be a variant or special release
                    break
            
            return True
            
        except ValueError:
            # Non-numeric card numbers (like promos)
            return True
    
    def suggest_corrections(self, card_name: str, set_name: str, confidence: float) -> Optional[str]:
        """
        Suggest potential corrections for low confidence matches
        
        Returns:
            Suggestion string or None
        """
        suggestions = []
        
        # Check for common patterns
        if confidence < 0.7:
            # Check if this might be a promo
            if any(term in card_name.lower() for term in ['promo', 'staff', 'championship', 'winner']):
                suggestions.append("Consider checking promo sets")
            
            # Check for McDonald's patterns
            common_mcdonalds = ['pikachu', 'eevee', 'charmander', 'squirtle', 'bulbasaur', 'togepi']
            if any(pokemon in card_name.lower() for pokemon in common_mcdonalds):
                suggestions.append("Common McDonald's promo - check McDonald's Collection sets")
            
            # Check for BREAK cards
            if 'break' in card_name.lower() or ('xy' in set_name.lower() and confidence < 0.5):
                suggestions.append("Possible BREAK card - these are often misidentified")
        
        return " | ".join(suggestions) if suggestions else None
    
    def detect_and_correct_promo_patterns(self, card_name: str, set_name: str, card_number: str) -> Tuple[str, str, Optional[str]]:
        """
        Detect promo patterns in card numbers and correct set names accordingly
        
        Returns:
            Tuple of (corrected_set_name, corrected_number, reason)
        """
        import re
        
        # Check if card number indicates a promo
        promo_pattern = re.match(r'^(BW|XY|SM|SWSH|SVP?|SV)(\d+)', card_number, re.IGNORECASE)
        if promo_pattern:
            prefix = promo_pattern.group(1).upper()
            number = promo_pattern.group(2)
            
            # Map prefix to correct promo set name
            promo_set_map = {
                'BW': 'BW Black Star Promos',
                'XY': 'XY Black Star Promos',
                'SM': 'SM Black Star Promos',
                'SWSH': 'SWSH Black Star Promos',
                'SV': 'Scarlet & Violet Promos',
                'SVP': 'Scarlet & Violet Promos'
            }
            
            if prefix in promo_set_map:
                correct_set = promo_set_map[prefix]
                correct_number = f"{prefix}{number.zfill(3) if len(number) < 3 else number}"
                
                if set_name != correct_set:
                    logger.info(f"   🎯 Promo pattern detected: {card_number} → {correct_set}")
                    return correct_set, correct_number, f"Promo number {correct_number} indicates {correct_set}"
        
        # Check for Staff/Championship patterns
        if any(term in card_name.lower() for term in ['staff', 'championship', 'city', 'state', 'regional', 'worlds']):
            if 'black star promo' not in set_name.lower() and 'promo' not in set_name.lower():
                logger.info(f"   🏆 Tournament promo detected in non-promo set")
                # Try to determine era from card characteristics
                if any(era in set_name.lower() for era in ['sun & moon', 'sm']):
                    return 'SM Black Star Promos', card_number, "Tournament promos are in Black Star sets"
                elif any(era in set_name.lower() for era in ['xy']):
                    return 'XY Black Star Promos', card_number, "Tournament promos are in Black Star sets"
                elif any(era in set_name.lower() for era in ['sword & shield', 'swsh']):
                    return 'SWSH Black Star Promos', card_number, "Tournament promos are in Black Star sets"
        
        # Check for League promo patterns
        if 'league' in card_name.lower() and 'promo' not in set_name.lower():
            logger.info(f"   🏅 League promo detected in non-promo set")
            # Determine era and suggest correct promo set
            # (Similar logic as above)
        
        return set_name, card_number, None