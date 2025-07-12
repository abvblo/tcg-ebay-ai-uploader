"""Price calculation logic"""

from decimal import Decimal
from typing import Union

from ..models import ProcessingConfig


class PriceCalculator:
    def __init__(self, config: ProcessingConfig):
        self.markup_percentage = config.markup_percentage
        self.minimum_floor = config.minimum_price_floor

    def calculate_final_price(self, base_price: Union[float, int, str, Decimal]) -> float:
        """Apply markup and minimum floor to base price"""
        # Convert to float to handle different input types
        if isinstance(base_price, Decimal):
            base_price = float(base_price)
        elif isinstance(base_price, str):
            base_price = float(base_price)
        elif isinstance(base_price, int):
            base_price = float(base_price)

        # Apply markup
        marked_up_price = base_price * self.markup_percentage

        # Apply minimum floor
        final_price = max(marked_up_price, self.minimum_floor)

        # Use proper decimal rounding for financial calculations
        return round(final_price, 2)
