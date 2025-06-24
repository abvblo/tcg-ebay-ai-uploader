"""Price calculation logic"""

from ..models import ProcessingConfig

class PriceCalculator:
    def __init__(self, config: ProcessingConfig):
        self.markup_percentage = config.markup_percentage
        self.minimum_floor = config.minimum_price_floor
    
    def calculate_final_price(self, base_price: float) -> float:
        """Apply markup and minimum floor to base price"""
        # Apply markup
        marked_up_price = base_price * self.markup_percentage
        
        # Apply minimum floor
        final_price = max(marked_up_price, self.minimum_floor)
        
        return round(final_price, 2)