#!/usr/bin/env python3
"""Debug the finish information flow from Ximilar to final output"""

import sys
import json
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

def debug_butterfree_finish():
    """Debug what happens to Butterfree's finish information"""
    
    print("🔍 DEBUGGING BUTTERFREE FINISH FLOW")
    print("=" * 50)
    
    # Load the Ximilar response for Butterfree
    butterfree_response_file = "output/ximilar_debug/20250704_142429_Butterfree_response.json"
    
    if not Path(butterfree_response_file).exists():
        print(f"❌ Butterfree response file not found: {butterfree_response_file}")
        return
    
    with open(butterfree_response_file, 'r') as f:
        ximilar_data = json.load(f)
    
    print("1️⃣ XIMILAR RESPONSE:")
    response = ximilar_data.get('response', {})
    records = response.get('records', [])
    if records:
        record = records[0]
        objects = record.get('_objects', [])
        if objects:
            card_obj = objects[0]
            tags = card_obj.get('_tags', {})
            foil_holo_tags = tags.get('Foil/Holo', [])
            
            print(f"   Foil/Holo tags: {foil_holo_tags}")
            
            if foil_holo_tags:
                finish_tag = max(foil_holo_tags, key=lambda x: x.get('prob', 0))
                print(f"   Best finish: {finish_tag['name']} (prob: {finish_tag['prob']:.3f})")
                
                # Test the Ximilar extraction
                from src.api.ximilar import XimilarClient
                ximilar_client = XimilarClient("dummy", "dummy")
                extracted_finish = ximilar_client._extract_finish_from_ximilar(card_obj)
                print(f"   Extracted finish: '{extracted_finish}'")
    
    print()
    print("2️⃣ TESTING EBAY FORMATTER:")
    from src.config import Config
    from src.output.ebay_formatter import EbayFormatter
    from src.models import CardData
    
    config = Config()
    ebay_formatter = EbayFormatter(config)
    
    # Test different finish values
    test_finishes = ['Reverse Holo', 'Holo', 'Normal', 'Non-Holo', '']
    
    for test_finish in test_finishes:
        test_card = CardData(
            name="Test Card",
            set_name="Test Set", 
            number="1/1",
            rarity="Rare",
            game="Pokémon",
            confidence=0.95,
            finish=test_finish,
            unique_characteristics=[],
            api_price=5.00,
            final_price=6.50,
            price_source="Test",
            tcgplayer_link="",
            image_urls=[],
            primary_image_url=""
        )
        
        formatted_finish = ebay_formatter._get_finish_value(test_card)
        print(f"   Input: '{test_finish}' → Output: '{formatted_finish}'")
    
    print()
    print("3️⃣ CHECKING EXCEL OUTPUT:")
    import pandas as pd
    
    try:
        df = pd.read_excel('output/tcg_listings_20250708_001540.xlsx')
        butterfree_row = df[df['C:Card Name'] == 'Butterfree']
        
        if not butterfree_row.empty:
            row = butterfree_row.iloc[0]
            print(f"   Excel finish: '{row['C:Finish']}'")
            print(f"   Excel title: '{row['*Title']}'")
            print(f"   Excel rarity: '{row['C:Rarity']}'")
        else:
            print("   ❌ Butterfree not found in Excel output")
    except Exception as e:
        print(f"   ❌ Error reading Excel: {e}")
    
    print()
    print("4️⃣ RECOMMENDED FIXES:")
    print("   Based on the analysis above, the issue is likely:")
    print("   1. Ximilar correctly detects 'Reverse Holo'")
    print("   2. But finish gets overridden somewhere in the pipeline")
    print("   3. Need to preserve Ximilar finish detection through the entire flow")

if __name__ == "__main__":
    debug_butterfree_finish()