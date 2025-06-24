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
        """Format card data for eBay upload"""
        # Format image URLs with pipe delimiter
        image_url = ""
        if card.image_urls:
            urls_with_cache_bust = [f"{url}?cache-bust={i}" for i, url in enumerate(card.image_urls)]
            image_url = "|".join(urls_with_cache_bust)
        
        # Log the TCGPlayer link we're putting in the Excel
        logger.info(f"   📝 Excel TCGPlayer link for {card.name}: {card.tcgplayer_link}")
        
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
            'C:Finish': card.finish if card.finish else '',
            'C:Features': ', '.join(card.unique_characteristics) if card.unique_characteristics else '',
            
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
        # Check for multiple images
        multi_image_note = ""
        if len(card.image_urls) > 1:
            multi_image_note = '\n  <p><em>📸 Multiple views available - see all images above for front and back of card.</em></p>'
        
        # Build card details
        details = []
        if card.hp:
            details.append(f"<strong>HP:</strong> {card.hp}")
        if card.types:
            details.append(f"<strong>Type:</strong> {', '.join(card.types)}")
        if card.rarity:
            details.append(f"<strong>Rarity:</strong> {card.rarity}")
        if card.unique_characteristics:
            details.append(f"<strong>Special:</strong> {', '.join(card.unique_characteristics)}")
        if card.artist:
            details.append(f"<strong>Artist:</strong> {card.artist}")
        
        details_html = ""
        if details:
            details_html = "\n  <p>" + " | ".join(details) + "</p>"
        
        return f"""<div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333;">
  <h2 style="color:#2e8b57;">Real Images. Real Cards. No Surprises.</h2>
  <p>Each card you see is scanned with our <strong>high-resolution imaging setup</strong> — <span style="color:#cc0000;">no stock photos here.</span></p>
  <p><strong>You'll receive the exact card pictured</strong>, and every listing is carefully inspected to meet our <strong>Near Mint to Lightly Played (NM/LP)</strong> quality standard.</p>{multi_image_note}
  <p><span style="color:#555;">Heads up:</span> Our scanner captures edgewear and whitening clearly, but extremely light surface marks may not always be visible. Questions? We've got your back — just send a message.</p>{details_html}
  <hr style="border-top:1px solid #ccc;">
  <h2 style="color:#2e8b57;">What NM/LP Means</h2>
  <p>We personally inspect every card to ensure it's in clean, collectible condition — ready to sleeve, play, or display.</p>
  <hr style="border-top:1px solid #ccc;">
  <h2 style="color:#2e8b57;">Combined Shipping Made Easy</h2>
  <p>Buying multiple cards? Add them to your cart and eBay will automatically combine shipping.</p>
  <hr style="border-top:1px solid #ccc;">
  <h2 style="color:#2e8b57;">We're Here to Help</h2>
  <p>Got questions? Just shoot us a message — we love talking cards!</p>
  <p><strong>- AboveBelow Fam</strong></p>
</div>"""