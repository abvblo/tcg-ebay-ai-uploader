"""Special pricing logic for promotional and McDonald's cards"""

from typing import Dict, Optional, Tuple

from ..utils.logger import logger


class PromoPricingCalculator:
    """Handle special pricing for promotional cards without API data"""

    # McDonald's Collection pricing tiers based on card type
    MCDONALDS_PRICING = {
        # Base prices for McDonald's promos by rarity/type
        "holo": 3.99,
        "holofoil": 3.99,
        "non-holo": 2.49,
        "normal": 2.49,
        "promo": 2.99,
        "default": 2.49,
    }

    # Special promo set pricing
    PROMO_SET_PRICING = {
        # Pattern matching for set names
        "mcdonald": MCDONALDS_PRICING,
        "burger king": {"default": 2.99},
        "general mills": {"default": 3.49},
        "toys r us": {"default": 3.99},
        "pokemon center": {"default": 4.99},
        "pokemon go": {"default": 2.99},
        "celebrations": {"default": 3.99},
        "pokemon rumble": {"default": 2.49},
        "25th anniversary": {"default": 4.99},
    }

    # High-value promo indicators
    HIGH_VALUE_PROMO_KEYWORDS = [
        "staff",
        "championship",
        "worlds",
        "regional",
        "national",
        "winner",
        "participant",
        "judge",
        "professor",
        "league leader",
        "prerelease",
        "launch",
    ]

    def get_fallback_price(
        self,
        card_name: str,
        set_name: str,
        rarity: str = None,
        card_number: str = None,
        unique_characteristics: list = None,
    ) -> Tuple[float, str]:
        """
        Get fallback price for promotional cards without market data

        Returns:
            Tuple of (price, price_source)
        """
        set_name_lower = set_name.lower() if set_name else ""
        card_name_lower = card_name.lower() if card_name else ""
        rarity_lower = rarity.lower() if rarity else ""

        # Check for high-value promotional cards first
        if self._is_high_value_promo(card_name_lower, set_name_lower, unique_characteristics):
            price = 19.99  # High value promo base price
            source = "High-Value Promo Estimate"
            logger.info(f"   💎 High-value promo detected: ${price}")
            return price, source

        # Check for McDonald's Collection specifically
        if self._is_mcdonalds_card(set_name_lower, card_number):
            price = self._get_mcdonalds_price(rarity_lower, unique_characteristics)
            source = "McDonald's Collection Estimate"
            logger.info(f"   🍟 McDonald's promo pricing: ${price}")
            return price, source

        # Check other known promo sets
        for promo_key, pricing_dict in self.PROMO_SET_PRICING.items():
            if promo_key in set_name_lower:
                # Try to match rarity/type first
                price = pricing_dict.get(rarity_lower, pricing_dict.get("default", 2.99))
                source = f"{promo_key.title()} Promo Estimate"
                logger.info(f"   🎁 {source}: ${price}")
                return price, source

        # General promo card pricing based on characteristics
        if "promo" in set_name_lower or self._has_promo_number(card_number):
            if any(
                char in str(unique_characteristics).lower() for char in ["holo", "foil", "reverse"]
            ):
                price = 3.49
                source = "Generic Holo Promo Estimate"
            else:
                price = 2.49
                source = "Generic Promo Estimate"

            logger.info(f"   🎯 {source}: ${price}")
            return price, source

        # Default fallback for unrecognized cards
        logger.warning(f"   ⚠️ No specific promo pricing found, using default")
        return 5.00, "Default (No Market Data)"

    def _is_mcdonalds_card(self, set_name: str, card_number: str) -> bool:
        """Check if this is a McDonald's promotional card"""
        # Direct set name check
        if "mcdonald" in set_name or "mc donald" in set_name:
            return True

        # Check card number patterns (McDonald's often uses small set numbers)
        if card_number and "/" in card_number:
            try:
                num, total = card_number.split("/")
                total_int = int(total)
                # McDonald's sets typically have 12-25 cards
                if 6 <= total_int <= 25 and "collection" in set_name:
                    return True
            except ValueError:
                pass

        return False

    def _get_mcdonalds_price(self, rarity: str, characteristics: list) -> float:
        """Get specific McDonald's card pricing"""
        # Check for holo characteristics
        if characteristics:
            char_str = " ".join(str(c).lower() for c in characteristics)
            if any(holo_term in char_str for holo_term in ["holo", "foil", "shiny"]):
                return self.MCDONALDS_PRICING["holo"]

        # Check rarity
        if rarity:
            for rarity_key, price in self.MCDONALDS_PRICING.items():
                if rarity_key in rarity:
                    return price

        return self.MCDONALDS_PRICING["default"]

    def _is_high_value_promo(self, card_name: str, set_name: str, characteristics: list) -> bool:
        """Check if this is a high-value promotional card"""
        # Check card name and set name for high-value keywords
        combined_text = f"{card_name} {set_name}"
        if characteristics:
            combined_text += " " + " ".join(str(c).lower() for c in characteristics)

        return any(keyword in combined_text for keyword in self.HIGH_VALUE_PROMO_KEYWORDS)

    def _has_promo_number(self, card_number: str) -> bool:
        """Check if card number indicates a promo"""
        if not card_number:
            return False

        # Common promo number patterns
        import re

        promo_patterns = [
            r"^(BW|XY|SM|SWSH|SV)\d+$",  # Pokemon promo patterns
            r"^PR-",  # Generic promo prefix
            r"PROMO",  # Contains PROMO
            r"^P\d+",  # Starts with P and numbers
        ]

        return any(re.match(pattern, card_number, re.IGNORECASE) for pattern in promo_patterns)
