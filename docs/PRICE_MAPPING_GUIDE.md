# Pokemon TCG Price Mapping Guide

This guide explains how the flexible price mapping system works and how to extend it for new card variations.

## How It Works

The system uses a hierarchical approach to determine the correct TCGPlayer price category based on card characteristics:

1. **Special Combinations** - Checked first (e.g., Shadowless + 1st Edition)
2. **Individual Characteristics** - Each characteristic maps to multiple price categories
3. **Set-Specific Rules** - Applied based on the card's set
4. **Exclusion Rules** - Remove inappropriate categories
5. **Default Fallback** - Standard categories as last resort

## Examples

### Example 1: Regular Unlimited Cubone from Jungle
- Characteristics: None
- Process:
  1. No special combinations
  2. No individual characteristics
  3. No set-specific rules for Jungle
  4. Exclusion rules remove 1st Edition categories
  5. Uses default categories: `['unlimited', 'unlimitedHolofoil', 'normal', ...]`
- **Result**: Selects 'unlimited' price ($0.36)

### Example 2: 1st Edition Shadowless Charizard from Base Set
- Characteristics: ['1st Edition', 'Shadowless']
- Process:
  1. Special combination found: 'shadowless+1st edition'
  2. Adds: `['shadowless1stEdition', 'shadowlessFirst', '1stEdition']`
  3. Individual mappings add more 1st Edition and Shadowless categories
  4. No exclusions (has 1st Edition)
- **Result**: Selects 'shadowless1stEdition' price if available

### Example 3: Staff Stamped Promo Pikachu
- Characteristics: ['Staff', 'Stamped', 'Promo']
- Process:
  1. Special combination 'staff+promo' adds: `['staffPromo', 'staff', 'promo']`
  2. Individual mappings add stamped and promo categories
  3. No set-specific rules
  4. No exclusions (is a promo)
- **Result**: Selects 'staffPromo' or 'staff' price

### Example 4: Japanese Reverse Holo from Modern Set
- Characteristics: ['Reverse Holo']
- Language: 'Japanese'
- Process:
  1. No special combinations
  2. 'Reverse Holo' adds: `['reverseHolofoil', 'holofoil', 'normal']`
  3. Language adds: `['japanese', 'normal']`
  4. Categories prioritized: Japanese categories first, then reverse holo
- **Result**: Selects 'japanese' price if available, otherwise 'reverseHolofoil'

## Adding New Mappings

### 1. Add a New Characteristic Mapping

In `price_mappings.py`, add to `CHARACTERISTIC_MAPPINGS`:

```python
'galaxy foil': ['galaxyFoil', 'holofoil', 'normal'],
'textured': ['textured', 'fullArt', 'holofoil'],
```

### 2. Add a Special Combination

For cards with multiple special characteristics:

```python
COMBINATION_RULES = {
    # ... existing rules ...
    'textured+full art': {
        'categories': ['texturedFullArt', 'textured', 'fullArt'],
        'requires': ['textured', 'full art']
    },
}
```

### 3. Add Set-Specific Rules

For sets with special pricing structures:

```python
SET_SPECIFIC_RULES = {
    # ... existing rules ...
    'crown zenith': {
        'additional_categories': ['crownZenith', 'galarian'],
        'exclude_categories': ['1stEdition']  # Modern set, no 1st Edition
    },
}
```

### 4. Add Exclusion Rules

For new category types that should be excluded under certain conditions:

```python
EXCLUSION_RULES = {
    # ... existing rules ...
    'not_textured': [
        'textured', 'texturedFullArt', 'texturedRare'
    ],
}
```

## TCGPlayer Price Category Patterns

Common TCGPlayer price category patterns:
- Base: `normal`, `holofoil`, `nonHolo`
- Edition: `1stEdition`, `unlimited`, `shadowless`
- Combinations: `1stEditionHolofoil`, `unlimitedHolofoil`
- Special: `reverseHolofoil`, `promo`, `staff`
- Language: `japanese`, `german`, `french`
- Modern: `galaxyFoil`, `textured`, `goldRare`

## Debugging

The system logs the price selection process:
```
💳 Available price categories: ['1stEdition', 'unlimited']
🎯 Card characteristics: 1st Edition, Shadowless
🔍 Checking price categories in order: ['shadowless1stEdition', '1stEdition', ...]
💰 Using market price from '1stEdition': $45.00
```

## Best Practices

1. **Order Matters**: List categories from most specific to least specific
2. **Always Include Fallbacks**: End with general categories like 'normal'
3. **Test Combinations**: Some characteristics conflict (e.g., Base Set 2 + 1st Edition)
4. **Use Actual TCGPlayer Categories**: Check TCGPlayer API responses for real category names
5. **Document Special Cases**: Add comments for unusual mappings

## Common Issues and Solutions

### Issue: Wrong Edition Price
- **Cause**: Card identified as regular but priced as 1st Edition
- **Solution**: Check `unique_characteristics` detection in Ximilar

### Issue: Missing Price Category
- **Cause**: TCGPlayer uses different category name than expected
- **Solution**: Log available categories and update mappings

### Issue: Language Variants
- **Cause**: Non-English cards using English prices
- **Solution**: Ensure language is passed correctly from identification