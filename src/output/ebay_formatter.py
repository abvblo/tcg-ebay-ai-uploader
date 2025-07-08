"""eBay data formatting"""

import time
from typing import Dict, Any
from ..models import CardData
from ..config import Config
from ..utils.logger import logger

class EbayFormatter:
    def __init__(self, config: Config):
        self.config = config
        self.business_policies = config.business_policies
    
    def format_card(self, card: CardData, title: str, index: int) -> Dict[str, Any]:
        """Format card data for eBay upload - ENHANCED VERSION"""
        # Format image URLs with pipe delimiter
        image_url = ""
        if card.image_urls:
            urls_with_cache_bust = [f"{url}?cache-bust={i}" for i, url in enumerate(card.image_urls)]
            image_url = "|".join(urls_with_cache_bust)
        
        # Extract year from release date
        year_manufactured = self._extract_year(card)
        
        # Determine if vintage (20+ years old)
        is_vintage = self._is_vintage(year_manufactured)
        
        # Get card size
        card_size = self._get_card_size(card)
        
        # Get country/region of manufacture
        country_manufacture = self._get_country_manufacture(card)
        
        # Get defense/toughness for MTG cards
        defense_toughness = self._get_defense_toughness(card)
        
        return {
            # Required eBay fields
            '*Action(SiteID=US|Country=US|Currency=USD|Version=1193)': 'Add',
            'CustomLabel': f"TCG_{int(time.time())}_{index}",
            '*Category': '183454',  # CCG Individual Cards
            'StoreCategory': '',
            '*Title': title,
            'Subtitle': '',
            
            # Condition
            '*ConditionID': '4000',  # Near Mint or better
            'CD:Card Condition - (ID: 40001)': '400010',
            
            # Item specifics
            '*C:Game': f'{card.game} TCG',
            'C:Card Name': card.name,
            'C:Character': card.name.split()[0] if card.name else '',
            'C:Set': card.set_name,
            'C:Rarity': card.rarity,
            'C:Card Number': card.number,
            'C:Graded': 'No',
            'C:Manufacturer': self._get_manufacturer(card.game),
            'C:Autographed': 'No',
            'C:Language': card.language,
            'C:Finish': self._get_finish_value(card),
            'C:Features': ', '.join(card.unique_characteristics) if card.unique_characteristics else '',
            
            # NEW FIELDS
            'C:Card Size': card_size,
            'C:Year Manufactured': year_manufactured if year_manufactured else '',
            'C:Vintage': 'Yes' if is_vintage else 'No',
            'C:Country/Region of Manufacture': country_manufacture,
            'C:Defense/Toughness': defense_toughness,
            
            # Pokemon/MTG specific
            'C:HP': card.hp or '',
            'C:Card Type': ', '.join(card.subtypes) if card.subtypes else '',
            'C:Attribute/MTG:Color': ', '.join(card.types) if card.types else '',
            
            # Images and description
            'PicURL': image_url,
            '*Description': self._generate_description(card),
            
            # Pricing and format
            '*Format': 'FixedPrice',
            '*Duration': 'GTC',
            '*StartPrice': card.final_price,
            '*Quantity': 1,
            'BestOfferEnabled': '0',
            
            # Location
            '*Location': 'Vista, CA',
            'PostalCode': '92083',
            '*DispatchTimeMax': '2',
            
            # Business policies
            'PaymentProfileName': self._get_payment_policy(),
            'ShippingProfileName': self._get_shipping_policy(card.final_price),
            'ReturnProfileName': self._get_return_policy(),
            
            # Tracking columns
            'ConfidenceScore': f"{card.confidence:.3f}",
            'ReviewFlag': card.review_flag,
            'PriceSource': card.price_source,
            'TCGPlayerLink': card.tcgplayer_link,
            'ProcessingNotes': card.processing_notes,
            'ImageCount': len(card.image_urls)
        }
    
    def _get_finish_value(self, card: CardData) -> str:
        """Get finish value with support for all finish types"""
        if card.finish:
            # Map finish values to eBay-acceptable values
            finish_mapping = {
                'Reverse Holo': 'Reverse Holo',
                'Holo': 'Holo',
                'Holofoil': 'Holo',
                'Normal': 'Non-Holo',
                'Non-Holo': 'Non-Holo',
                'No Holo': 'Non-Holo',
                'Foil': 'Holo',
                'Non-Foil': 'Non-Holo'
            }
            
            mapped_finish = finish_mapping.get(card.finish, card.finish)
            if mapped_finish in ['Reverse Holo', 'Holo', 'Non-Holo']:
                return mapped_finish
        
        # Smart defaults based on game and rarity
        if card.game.lower() in ['pokémon', 'pokemon']:
            # For Pokemon, check if it's likely to be holo based on rarity
            rarity_lower = card.rarity.lower() if card.rarity else ''
            if any(term in rarity_lower for term in ['holo', 'rare', 'ultra', 'secret', 'rainbow']):
                return 'Holo'
            else:
                return 'Non-Holo'
        elif card.game.lower() in ['magic: the gathering', 'mtg']:
            return 'Non-Foil'
        else:
            return 'Non-Holo'
    
    def _extract_year(self, card: CardData) -> str:
        """Extract year manufactured from release date"""
        if hasattr(card, 'release_date') and card.release_date:
            try:
                # Release date could be YYYY-MM-DD or YYYY/MM/DD
                date_str = str(card.release_date)
                if '/' in date_str:
                    year = date_str.split('/')[0]
                elif '-' in date_str:
                    year = date_str.split('-')[0]
                else:
                    year = date_str[:4]  # Just take first 4 chars
                
                # Validate it's a reasonable year
                year_int = int(year)
                if 1993 <= year_int <= 2030:  # Pokemon TCG started in 1996, MTG in 1993
                    return year
            except:
                pass
        
        # Fallback: try to extract from set name for known patterns
        set_name = card.set_name.lower() if card.set_name else ''
        
        # Common year patterns in set names
        import re
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', card.set_name)
        if year_match:
            return year_match.group(1)
        
        # Known set release years (partial list for common sets)
        set_years = {
            'base set': '1999',
            'jungle': '1999',
            'fossil': '1999',
            'base set 2': '2000',
            'team rocket': '2000',
            'gym heroes': '2000',
            'gym challenge': '2000',
            'neo genesis': '2000',
            'neo discovery': '2001',
            'neo revelation': '2001',
            'neo destiny': '2001',
            'legendary collection': '2002',
            'expedition': '2002',
            'aquapolis': '2003',
            'skyridge': '2003',
            'dragon vault': '2012',
            # MTG sets
            'alpha': '1993',
            'beta': '1993',
            'unlimited': '1993',
            'revised': '1994',
            'fourth edition': '1995',
            '4th edition': '1995',
            'ice age': '1995',
            'mirage': '1996',
            'tempest': '1997',
            'urza': '1998',
            'mercadian': '1999',
            'invasion': '2000',
            'odyssey': '2001',
            'onslaught': '2002',
            'mirrodin': '2003',
            'kamigawa': '2004',
            'ravnica': '2005',
            'time spiral': '2006',
            'lorwyn': '2007',
            'shadowmoor': '2008',
            'shards of alara': '2008',
            'zendikar': '2009',
            'scars of mirrodin': '2010',
            'innistrad': '2011',
            'return to ravnica': '2012',
            'theros': '2013',
            'khans of tarkir': '2014',
            'battle for zendikar': '2015',
            'shadows over innistrad': '2016',
            'kaladesh': '2016',
            'amonkhet': '2017',
            'ixalan': '2017',
            'dominaria': '2018',
            'guilds of ravnica': '2018',
            'war of the spark': '2019',
            'throne of eldraine': '2019',
            'theros beyond death': '2020',
            'ikoria': '2020',
            'zendikar rising': '2020',
            'kaldheim': '2021',
            'strixhaven': '2021',
            'innistrad midnight hunt': '2021',
            'innistrad crimson vow': '2021',
            'kamigawa neon dynasty': '2022',
            'streets of new capenna': '2022',
            'dominaria united': '2022',
            'brothers war': '2022',
            'phyrexia all will be one': '2023',
            'march of the machine': '2023',
            'wilds of eldraine': '2023',
            'lost caverns of ixalan': '2023',
        }
        
        # Check if set name contains any known set
        for known_set, year in set_years.items():
            if known_set in set_name:
                return year
        
        return ''
    
    def _is_vintage(self, year_str: str) -> bool:
        """Determine if card is vintage (20+ years old)"""
        if not year_str:
            return False
        
        try:
            year = int(year_str)
            current_year = 2025  # From your system prompt
            age = current_year - year
            return age >= 20
        except:
            return False
    
    def _get_card_size(self, card: CardData) -> str:
        """Get card size - most TCG cards are standard size"""
        # Check for oversized cards (usually promos or special editions)
        set_name = card.set_name.lower() if card.set_name else ''
        card_name = card.name.lower() if card.name else ''
        
        # Known oversized cards/sets
        oversized_indicators = [
            'oversized',
            'jumbo',
            'box topper',
            'promo card',
            'world championship',
            'celebration',
            'trophy',
        ]
        
        for indicator in oversized_indicators:
            if indicator in set_name or indicator in card_name:
                return 'Oversized'
        
        # Special promo cards that are often oversized
        if card.unique_characteristics:
            chars_lower = [c.lower() for c in card.unique_characteristics]
            if any('trophy' in c or 'championship' in c or 'winner' in c for c in chars_lower):
                return 'Oversized'
        
        # Default is standard size
        return 'Standard'
    
    def _get_country_manufacture(self, card: CardData) -> str:
        """Get country/region of manufacture based on game and language"""
        # For Japanese cards
        if card.language.lower() in ['japanese', 'jp']:
            return 'Japan'
        
        # For other languages
        language_countries = {
            'german': 'Belgium',  # EU printing
            'french': 'Belgium',
            'italian': 'Belgium',
            'spanish': 'Belgium',
            'portuguese': 'Belgium',
            'dutch': 'Belgium',
            'russian': 'Belgium',
            'korean': 'Korea',
            'chinese': 'China',
        }
        
        if card.language.lower() in language_countries:
            return language_countries[card.language.lower()]
        
        # By game type and era
        if card.game.lower() in ['pokémon', 'pokemon']:
            # Check if it's a WOTC era card (1999-2003)
            year = self._extract_year(card)
            if year and int(year) <= 2003:
                return 'United States'  # WOTC printed in USA
            else:
                # Modern Pokemon cards are printed in USA or Belgium
                if 'promo' in card.set_name.lower():
                    return 'United States'
                else:
                    return 'United States'  # Most US cards printed in USA
        
        elif card.game.lower() in ['magic: the gathering', 'mtg']:
            # MTG printing locations vary by set and era
            year = self._extract_year(card)
            if year and int(year) <= 1995:
                return 'Belgium'  # Carta Mundi
            else:
                # Modern MTG printed in various locations
                return 'United States'  # Most common for US market
        
        # Default
        return 'United States'
    
    def _get_defense_toughness(self, card: CardData) -> str:
        """Get defense/toughness value (MTG only)"""
        # This is MTG-specific - Pokemon doesn't have defense/toughness
        if card.game.lower() not in ['magic: the gathering', 'mtg']:
            return ''
        
        # Check if we have toughness data from Scryfall
        if hasattr(card, 'toughness') and card.toughness:
            return str(card.toughness)
        
        return ''
    
    def _get_manufacturer(self, game: str) -> str:
        """Get manufacturer based on game"""
        manufacturers = {
            'Pokémon': 'Nintendo',
            'Pokemon': 'Nintendo',
            'Magic: The Gathering': 'Wizards of the Coast',
            'MTG': 'Wizards of the Coast',
            'Yu-Gi-Oh!': 'Konami',
            'Yu-Gi-Oh': 'Konami'
        }
        return manufacturers.get(game, 'Nintendo')
    
    def _get_payment_policy(self) -> str:
        """Get payment policy name"""
        return self.business_policies.get('payment_policy_name', 'Immediate Payment (BIN)')
    
    def _get_shipping_policy(self, price: float) -> str:
        """Get shipping policy based on price"""
        if price < 20.00:
            return self.business_policies.get('shipping_policy_under_20', 'Standard Envelope 1oz (Free)')
        else:
            return self.business_policies.get('shipping_policy_over_20', 'Free Shipping US GA')
    
    def _get_return_policy(self) -> str:
        """Get return policy name"""
        return self.business_policies.get('return_policy_name', 'Returns Accepted')
    
    def _generate_description(self, card: CardData) -> str:
        """Generate HTML description"""
        # Format card number as Number/Total if possible
        card_number = card.number
        # The card.number might already be in "11/20" format from the API
        # If not, we'll use it as is
        
        # Extract year from release date if available (ensure only year)
        year = ''
        if hasattr(card, 'release_date') and card.release_date:
            try:
                # Release date could be YYYY-MM-DD or YYYY/MM/DD
                if '/' in str(card.release_date):
                    year = str(card.release_date).split('/')[0]
                elif '-' in str(card.release_date):
                    year = str(card.release_date).split('-')[0]
                else:
                    year = str(card.release_date)[:4]  # Just take first 4 chars
            except:
                year = ''
        # Fallback to year_manufactured if available
        if not year and hasattr(card, 'year_manufactured') and card.year_manufactured:
            year = str(card.year_manufactured)[:4]  # Ensure only 4 digits
        
        # Format game name properly
        game_name = card.game
        if game_name.lower() in ['pokémon', 'pokemon']:
            game_name = 'Pokémon TCG'
        elif game_name.lower() in ['magic: the gathering', 'mtg']:
            game_name = 'Magic: The Gathering'
        
        # Get artist name with fallback
        artist_name = card.artist if card.artist else 'Not Listed'
        
        # Build card details list items IN REQUESTED ORDER
        details_html = f"""  <ul style="margin-left: -20px;">
    <li><strong>Card Name:</strong> {card.name}</li>
    <li><strong>Game:</strong> {game_name}</li>
    <li><strong>Set:</strong> {card.set_name}</li>
    <li><strong>Card Number:</strong> {card_number}</li>
    <li><strong>Rarity:</strong> {card.rarity}</li>
    <li><strong>Condition:</strong> Near Mint / Lightly Played</li>
    <li><strong>Finish:</strong> {self._get_finish_value(card)}</li>"""
        
        # Add Features only if they exist
        if card.unique_characteristics and len(card.unique_characteristics) > 0:
            features_str = ', '.join(card.unique_characteristics)
            details_html += f"\n    <li><strong>Features:</strong> {features_str}</li>"
        
        # Add Year if available
        if year:
            details_html += f"\n    <li><strong>Year:</strong> {year}</li>"
        
        # Add Artist
        details_html += f"\n    <li><strong>Artist:</strong> {artist_name}</li>"
        
        details_html += "\n  </ul>"
        
        return f"""<div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333;">
  <h2 style="color:#2e8b57;">📸 Real Photos. Real Cards. Zero Guesswork.</h2>
  <p>Every card you see is photographed using our <strong>high resolution scanner</strong> — no stock images or Photoshop tricks here. <span style="color:#cc0000;"><strong>What you see is what ships!</strong></span></p>
  <p><strong>✅ You'll receive this exact copy:</strong> Front and back are clearly shown — no mystery whitening, no surprises.</p>
  <p style="color:#555;"><em>NM/LP cards only — all are inspected by hand by a collector, not a robot.</em></p>
  <p style="font-size:13px;">🧐 <strong>Note:</strong> Our scanner picks up edgewear and whitening clearly, but faint surface scratches may not always be visible. Questions? We're lightning-fast on messages!</p>
  
  <hr style="border-top:1px solid #ccc;">
  <h2 style="color:#2e8b57;">🧠 Card Details</h2>
{details_html}
  <hr style="border-top:1px solid #ccc;">
  <h2 style="color:#2e8b57;">💎 What NM/LP Means</h2>
  <p>Our NM/LP standard means <strong>clean, tournament-ready cards</strong> with only light signs of handling. No creases. No ink. No trash. Every card is sleeve-worthy — or binder-ready if you're a collector.</p>
  <p><em>If we wouldn't buy it ourselves, we don't list it.</em></p>
  <hr style="border-top:1px solid #ccc;">
  <h2 style="color:#2e8b57;">🚚 Shipping & Bundle Discounts</h2>
  <p><strong>FREE fast shipping!</strong> Orders ship same day or next business day.</p>
  <p>📬 <strong>Under $20:</strong> Ships via eBay Standard Envelope with tracking and protective packaging.</p>
  <p>📦 <strong>$20 and over:</strong> Ships via USPS Ground Advantage with full tracking and extra protection.</p>
  <p>🛒 Buying multiple cards? Add to cart and eBay will auto-combine shipping to save you $$.</p>
  <hr style="border-top:1px solid #ccc;">
  <h2 style="color:#2e8b57;">🧾 Shop with Confidence</h2>
  <p>💬 Got questions? Shoot us a message anytime. We're not a warehouse — we're real collectors, just like you.</p>
  <p><strong>– The AboveBelow Fam</strong> 🃏💚</p>
</div>"""