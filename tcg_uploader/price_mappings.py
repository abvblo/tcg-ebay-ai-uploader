"""Price category mappings configuration for TCGPlayer API

This module contains the flexible configuration for mapping card characteristics
to TCGPlayer price categories. Easy to extend and maintain.
"""

from typing import Dict, List

class PriceMappingConfig:
    """Configuration for mapping card characteristics to price categories"""
    
    # Main characteristic mappings
    CHARACTERISTIC_MAPPINGS: Dict[str, List[str]] = {
        # Edition variants
        '1st edition': ['1stEdition', '1stEditionHolofoil', '1stEditionNormal'],
        'first edition': ['1stEdition', '1stEditionHolofoil', '1stEditionNormal'],
        'shadowless': ['shadowless', 'shadowlessHolofoil', 'shadowlessFirst'],
        'unlimited': ['unlimited', 'unlimitedHolofoil', 'normal', 'holofoil'],
        'base set 2': ['unlimited', 'normal'],  # Base Set 2 has no 1st Edition
        
        # Print variations
        'error': ['error', 'misprint', 'unlimited', 'normal'],
        'misprint': ['error', 'misprint', 'unlimited', 'normal'],
        'miscut': ['error', 'misprint', 'unlimited', 'normal'],
        'crimp': ['error', 'unlimited', 'normal'],
        'ink error': ['error', 'misprint', 'unlimited', 'normal'],
        
        # Special editions
        'staff': ['staff', 'promo', 'normal'],
        'stamped': ['stamped', 'promo', 'normal'],
        'promo': ['promo', 'promotional', 'normal'],
        'promotional': ['promo', 'promotional', 'normal'],
        'pre-release': ['prerelease', 'promo', 'normal'],
        'prerelease': ['prerelease', 'promo', 'normal'],
        'championship': ['championship', 'promo', 'normal'],
        'world championship': ['worldChampionship', 'championship', 'promo'],
        'tournament': ['tournament', 'promo', 'normal'],
        'league': ['league', 'promo', 'normal'],
        'winner': ['winner', 'promo', 'normal'],
        'city championship': ['cityChampionship', 'championship', 'promo'],
        'regional': ['regional', 'championship', 'promo'],
        'national': ['national', 'championship', 'promo'],
        
        # Holo variations
        'reverse holo': ['reverseHolofoil', 'holofoil', 'normal'],
        'reverse holofoil': ['reverseHolofoil', 'holofoil', 'normal'],
        'holo': ['holofoil', 'unlimited', 'normal'],
        'holofoil': ['holofoil', 'unlimited', 'normal'],
        'cosmos holo': ['cosmosHolo', 'holofoil', 'normal'],
        'cracked ice': ['crackedIce', 'holofoil', 'normal'],
        
        # Language variants
        'japanese': ['japanese', 'normal'],
        'german': ['german', 'normal'],
        'french': ['french', 'normal'],
        'italian': ['italian', 'normal'],
        'spanish': ['spanish', 'normal'],
        'korean': ['korean', 'normal'],
        'chinese': ['chinese', 'normal'],
        'portuguese': ['portuguese', 'normal'],
        'russian': ['russian', 'normal'],
        'dutch': ['dutch', 'normal'],
        
        # Other special cases
        'gold star': ['goldStar', 'holofoil', 'normal'],
        'shining': ['shining', 'holofoil', 'normal'],
        'crystal': ['crystal', 'holofoil', 'normal'],
        'amazing rare': ['amazingRare', 'holofoil', 'normal'],
        'secret rare': ['secretRare', 'holofoil', 'normal'],
        'rainbow rare': ['rainbowRare', 'secretRare', 'holofoil'],
        'gold rare': ['goldRare', 'secretRare', 'holofoil'],
        'full art': ['fullArt', 'holofoil', 'normal'],
        'alternate art': ['alternateArt', 'fullArt', 'holofoil'],
        'trainer gallery': ['trainerGallery', 'holofoil', 'normal'],
    }
    
    # Special combination rules
    COMBINATION_RULES: Dict[str, Dict[str, List[str]]] = {
        # When both characteristics are present, use these categories
        'shadowless+1st edition': {
            'categories': ['shadowless1stEdition', 'shadowlessFirst', '1stEdition'],
            'requires': ['shadowless', '1st edition']
        },
        'staff+promo': {
            'categories': ['staffPromo', 'staff', 'promo'],
            'requires': ['staff', 'promo']
        },
        'championship+promo': {
            'categories': ['championshipPromo', 'championship', 'promo'],
            'requires': ['championship', 'promo']
        },
    }
    
    # Set-specific rules
    SET_SPECIFIC_RULES: Dict[str, Dict[str, any]] = {
        'base set 2': {
            'exclude_categories': ['1stEdition', '1stEditionHolofoil', '1stEditionNormal'],
            'force_categories': ['unlimited', 'normal']
        },
        'evolutions': {
            # Evolutions can have special reprints
            'additional_categories': ['evolutions', 'normal']
        },
        'celebrations': {
            # Celebrations has special pricing
            'additional_categories': ['celebrations', 'normal']
        },
    }
    
    # Default fallback categories (in priority order)
    DEFAULT_CATEGORIES: List[str] = [
        'unlimited',
        'unlimitedHolofoil',
        'normal',
        'holofoil',
        'reverseHolofoil',
        'nonHolo',
        'common',
        'uncommon',
        'rare',
        'rareHolo'
    ]
    
    # Categories to skip for certain conditions
    EXCLUSION_RULES: Dict[str, List[str]] = {
        # If card is NOT 1st Edition, skip these categories
        'not_first_edition': [
            '1stEdition', '1stEditionHolofoil', '1stEditionNormal',
            'shadowless1stEdition', 'shadowlessFirst'
        ],
        # If card is NOT shadowless, skip these
        'not_shadowless': [
            'shadowless', 'shadowlessHolofoil', 'shadowlessFirst',
            'shadowless1stEdition'
        ],
        # If card is NOT a promo, skip these
        'not_promo': [
            'promo', 'promotional', 'staffPromo', 'championshipPromo',
            'prerelease', 'staff'
        ],
    }
    
    @classmethod
    def get_mapping(cls, characteristic: str) -> List[str]:
        """Get price categories for a specific characteristic"""
        return cls.CHARACTERISTIC_MAPPINGS.get(characteristic.lower(), [])
    
    @classmethod
    def get_combination_categories(cls, characteristics: List[str]) -> List[str]:
        """Get special categories for characteristic combinations"""
        categories = []
        chars_lower = [c.lower() for c in characteristics]
        
        for rule_name, rule_config in cls.COMBINATION_RULES.items():
            required = rule_config['requires']
            if all(req in chars_lower for req in required):
                categories.extend(rule_config['categories'])
        
        return categories
    
    @classmethod
    def apply_set_rules(cls, set_name: str, categories: List[str]) -> List[str]:
        """Apply set-specific rules to category list"""
        if not set_name:
            return categories
            
        set_lower = set_name.lower()
        
        for set_pattern, rules in cls.SET_SPECIFIC_RULES.items():
            if set_pattern in set_lower:
                # Apply exclusions
                if 'exclude_categories' in rules:
                    categories = [cat for cat in categories 
                                if cat not in rules['exclude_categories']]
                
                # Add additional categories
                if 'additional_categories' in rules:
                    categories.extend(rules['additional_categories'])
                
                # Force specific categories
                if 'force_categories' in rules:
                    categories = rules['force_categories'] + categories
        
        return categories
    
    @classmethod
    def apply_exclusion_rules(cls, characteristics: List[str], categories: List[str]) -> List[str]:
        """Apply exclusion rules based on what characteristics are NOT present"""
        chars_lower = [c.lower() for c in characteristics] if characteristics else []
        
        # Apply exclusion rules
        if not any('1st edition' in c or 'first edition' in c for c in chars_lower):
            exclude = cls.EXCLUSION_RULES.get('not_first_edition', [])
            categories = [cat for cat in categories if cat not in exclude]
        
        if not any('shadowless' in c for c in chars_lower):
            exclude = cls.EXCLUSION_RULES.get('not_shadowless', [])
            categories = [cat for cat in categories if cat not in exclude]
        
        if not any(promo_term in c for c in chars_lower 
                   for promo_term in ['promo', 'staff', 'championship', 'tournament']):
            exclude = cls.EXCLUSION_RULES.get('not_promo', [])
            categories = [cat for cat in categories if cat not in exclude]
        
        return categories