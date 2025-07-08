#!/usr/bin/env python3
"""Analyze finish information issues in the latest Excel output"""

import pandas as pd
import numpy as np
from pathlib import Path

def analyze_finish_issues():
    """Analyze finish vs title discrepancies"""
    
    # Read the latest Excel file
    excel_file = "output/tcg_listings_20250708_001540.xlsx"
    if not Path(excel_file).exists():
        print(f"❌ Excel file not found: {excel_file}")
        return
    
    df = pd.read_excel(excel_file)
    
    print('📊 DETAILED FINISH ANALYSIS')
    print('=' * 50)
    print(f'Total listings: {len(df)}')
    print()
    
    # Handle NaN values
    df['C:Finish'] = df['C:Finish'].fillna('Missing')
    
    # Analyze finish column
    print('🎯 FINISH COLUMN VALUES:')
    finish_counts = df['C:Finish'].value_counts()
    for finish, count in finish_counts.items():
        print(f'  {finish}: {count} cards')
    print()
    
    # Check specific cards that should have finish info
    print('🔍 SAMPLE TITLE VS FINISH ANALYSIS:')
    issues = []
    
    for i in range(min(20, len(df))):
        title = str(df['*Title'].iloc[i])
        finish = str(df['C:Finish'].iloc[i])
        card_name = str(df['C:Card Name'].iloc[i])
        rarity = str(df['C:Rarity'].iloc[i])
        
        # Check if finish info is in title
        finish_in_title = False
        if finish != 'Missing' and finish != 'nan':
            finish_in_title = finish.lower() in title.lower()
        
        status = '✅' if finish_in_title or finish == 'Missing' else '❌'
        
        if not finish_in_title and finish != 'Missing' and finish != 'nan':
            issues.append({
                'card': card_name,
                'finish': finish, 
                'title': title,
                'rarity': rarity
            })
        
        print(f'{status} {card_name} [{finish}] → "{title}"')
    
    print()
    print(f'📈 ISSUES FOUND: {len(issues)} cards in sample')
    
    # Count all issues
    total_issues = 0
    for i in range(len(df)):
        title = str(df['*Title'].iloc[i])
        finish = str(df['C:Finish'].iloc[i])
        
        if finish != 'Missing' and finish != 'nan' and finish.lower() not in title.lower():
            total_issues += 1
    
    print(f'📈 TOTAL ISSUES: {total_issues}/{len(df)} cards ({total_issues/len(df)*100:.1f}%)')
    print()
    
    # Check Reverse Holo specifically
    reverse_holo_cards = df[df['C:Finish'] == 'Reverse Holo']
    print(f'🌟 REVERSE HOLO CARDS ({len(reverse_holo_cards)}):')
    for _, card in reverse_holo_cards.iterrows():
        title = str(card['*Title'])
        card_name = str(card['C:Card Name'])
        has_reverse_in_title = 'reverse holo' in title.lower()
        status = '✅' if has_reverse_in_title else '❌'
        print(f'{status} {card_name}: "{title}"')
    
    print()
    
    # Check Non-Holo that might be wrong
    print('🔍 NON-HOLO CARDS THAT MIGHT BE WRONG:')
    non_holo_with_holo_rarity = df[
        (df['C:Finish'] == 'Non-Holo') & 
        (df['C:Rarity'].str.contains('Holo', case=False, na=False))
    ]
    
    print(f'Found {len(non_holo_with_holo_rarity)} Non-Holo cards with Holo rarity:')
    for _, card in non_holo_with_holo_rarity.head(10).iterrows():
        print(f'  {card["C:Card Name"]} - Rarity: {card["C:Rarity"]} - Finish: {card["C:Finish"]}')
    
    return issues

if __name__ == "__main__":
    analyze_finish_issues()