"""Pokemon card finish extraction logic"""

def extract_finish(card_data, price_category):
    """Extract finish information from Pokemon TCG API data"""
    
    # Debug logging
    from ..utils.logger import logger
    logger.debug(f"      🎨 Extracting finish - Price category: {price_category}")
    
    # Price category is the most reliable indicator
    if price_category:
        category_lower = price_category.lower()
        
        # Direct mappings from price categories
        if 'holofoil' in category_lower:
            return 'Holo'
        elif 'reverse' in category_lower:
            return 'Reverse Holo'
        elif '1st' in category_lower:
            return '1st Edition'
        
    # Check rarity for holo information
    rarity = card_data.get('rarity', '').lower()
    
    # Common holo rarities
    if any(term in rarity for term in ['holo', 'holofoil']):
        if 'reverse' in rarity:
            return 'Reverse Holo'
        else:
            return 'Holo'
    
    # Check subtypes for special cards
    subtypes = card_data.get('subtypes', [])
    for subtype in subtypes:
        subtype_lower = subtype.lower()
        
        # Full Art cards
        if 'full art' in subtype_lower or 'fullart' in subtype_lower:
            return 'Full Art'
        
        # Secret Rare
        if 'secret' in subtype_lower:
            return 'Secret Rare'
        
        # Rainbow
        if 'rainbow' in subtype_lower:
            return 'Rainbow'
        
        # Gold
        if 'gold' in subtype_lower:
            return 'Gold'
    
    # Check set-specific patterns
    set_data = card_data.get('set', {})
    set_name = set_data.get('name', '').lower()
    
    # Shining cards from specific sets
    if 'shining' in set_name and 'shining' in card_data.get('name', '').lower():
        return 'Shining'
    
    # EX, GX, V cards are typically holo
    card_name = card_data.get('name', '').lower()
    if any(suffix in card_name for suffix in [' ex', ' gx', ' v', ' vmax', ' vstar']):
        return 'Holo'
    
    # BREAK cards
    if 'break' in card_name:
        return 'Holo'
    
    # Promo cards often have special finishes
    if 'promo' in set_name:
        # Many promos are holo
        return 'Holo'
    
    # Default to non-holo for regular cards
    return 'Non-Holo'


def extract_features(card_data, price_category):
    """Extract special features/characteristics from card data"""
    features = []
    
    # Check for 1st Edition
    if price_category and '1st' in price_category.lower():
        features.append('1st Edition')
    
    # Check for Shadowless
    set_data = card_data.get('set', {})
    set_name = set_data.get('name', '').lower()
    card_name = card_data.get('name', '').lower()
    
    if 'base' in set_name and 'shadowless' in price_category.lower():
        features.append('Shadowless')
    
    # Check for Stamped cards
    # Many stamped cards come from specific sets or have patterns
    stamped_indicators = [
        'league' in set_name,
        'championship' in set_name,
        'worlds' in set_name,
        'regional' in set_name,
        'city championship' in set_name,
        'state championship' in set_name,
        # Specific stamped promos
        'staff' in card_name,
        'prerelease' in card_name,
        # Common stamped cards
        (card_name == 'wynaut' and 'legend maker' in set_name),  # Specific known stamped
    ]
    
    if any(stamped_indicators):
        features.append('Stamped')
    
    # Check for special stamps or marks
    if card_data.get('regulationMark'):
        # Regulation marks might indicate tournament legal status
        pass
    
    # Promo features
    if 'promo' in set_name:
        if 'staff' in card_name:
            features.append('Staff')
        elif 'prerelease' in card_name:
            features.append('Pre-release')
        # Many promos are stamped
        if not any(f == 'Stamped' for f in features):
            # Check if it's a known stamped promo pattern
            if any(term in card_name for term in ['league', 'championship', 'worlds']):
                features.append('Stamped')
    
    return features