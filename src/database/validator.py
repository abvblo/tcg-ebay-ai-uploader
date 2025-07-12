"""Validate Ximilar results against Pokemon card database"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from fuzzywuzzy import fuzz
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from .models import (
    CardVariation,
    PokemonCard,
    PokemonSet,
    ValidationRule,
    XimilarCorrection,
)

logger = logging.getLogger(__name__)


class DatabaseValidator:
    """Validate card identifications against the Pokemon database"""

    def __init__(self, session: Optional[Session] = None):
        self.session = session
        self.correction_cache = {}
        if session:
            self._load_corrections()

    def _load_corrections(self):
        """Load known corrections into memory"""
        corrections = self.session.query(XimilarCorrection).filter_by(verified=True).all()
        for correction in corrections:
            key = self._make_correction_key(correction.ximilar_result)
            self.correction_cache[key] = correction

    def _make_correction_key(self, ximilar_result: Dict[str, Any]) -> str:
        """Create a cache key from Ximilar result"""
        name = ximilar_result.get("name", "").lower().strip()
        set_name = ximilar_result.get("set", "").lower().strip()
        number = ximilar_result.get("number", "").strip()
        return f"{name}|{set_name}|{number}"

    def validate_card(self, ximilar_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a Ximilar result against the database

        Returns:
            {
                'is_valid': bool,
                'confidence_adjustment': float,  # Multiply Ximilar confidence by this
                'correct_card': PokemonCard or None,
                'correct_variation': CardVariation or None,
                'validation_notes': List[str],
                'suggested_correction': Dict or None
            }
        """
        result = {
            "is_valid": True,
            "confidence_adjustment": 1.0,
            "correct_card": None,
            "correct_variation": None,
            "validation_notes": [],
            "suggested_correction": None,
        }

        # If no database session, return default result
        if not self.session:
            result["validation_notes"].append("Database validation skipped - no session available")
            return result

        # Extract data from Ximilar
        name = ximilar_result.get("name", "").strip()
        set_name = ximilar_result.get("set_name", "").strip()
        number = ximilar_result.get("number", "").strip()
        confidence = ximilar_result.get("confidence", 0)

        # Check for known corrections first
        correction_key = self._make_correction_key(ximilar_result)
        if correction_key in self.correction_cache:
            correction = self.correction_cache[correction_key]
            if confidence <= correction.confidence_threshold:
                result["correct_card"] = correction.correct_card
                result["correct_variation"] = correction.correct_variation
                result["confidence_adjustment"] = 1.5  # Boost confidence for known corrections
                result["validation_notes"].append("Applied known correction")
                return result

        # Try exact match first
        exact_match = self._find_exact_match(name, set_name, number)
        if exact_match:
            result["correct_card"] = exact_match
            result["validation_notes"].append("Exact match found")

            # Check for specific variations
            variation = self._identify_variation(exact_match, ximilar_result)
            if variation:
                result["correct_variation"] = variation

            return result

        # Try fuzzy matching
        fuzzy_matches = self._find_fuzzy_matches(name, set_name, number)
        if fuzzy_matches:
            best_match, match_score = fuzzy_matches[0]

            if match_score > 90:  # High confidence fuzzy match
                result["correct_card"] = best_match
                result["confidence_adjustment"] = match_score / 100
                result["validation_notes"].append(f"Fuzzy match (score: {match_score})")

                # Suggest correction if confidence is low
                if confidence < 0.7:
                    result["suggested_correction"] = {
                        "name": best_match.name,
                        "set": best_match.set.name,
                        "number": best_match.number,
                    }
            elif match_score > 80 and confidence < 0.5:
                # Low confidence Ximilar + decent fuzzy match
                result["is_valid"] = False
                result["validation_notes"].append(
                    f"Low confidence with fuzzy match (score: {match_score})"
                )
                result["suggested_correction"] = {
                    "name": best_match.name,
                    "set": best_match.set.name,
                    "number": best_match.number,
                }

        # Run validation rules
        validation_issues = self._run_validation_rules(ximilar_result)
        if validation_issues:
            result["is_valid"] = False
            result["validation_notes"].extend(validation_issues)
            result["confidence_adjustment"] *= 0.5

        # Era validation
        era_issues = self._validate_era(name, set_name)
        if era_issues:
            result["is_valid"] = False
            result["validation_notes"].extend(era_issues)
            result["confidence_adjustment"] *= 0.3

        # If no match found and low confidence, mark as invalid
        if not result["correct_card"] and confidence < 0.6:
            result["is_valid"] = False
            result["validation_notes"].append("No database match and low confidence")

        return result

    def _find_exact_match(self, name: str, set_name: str, number: str) -> Optional[PokemonCard]:
        """Find exact card match in database"""
        # Try with exact set name first
        card = (
            self.session.query(PokemonCard)
            .join(PokemonSet)
            .filter(
                and_(
                    func.lower(PokemonCard.name) == name.lower(),
                    func.lower(PokemonSet.name) == set_name.lower(),
                    PokemonCard.number == number,
                )
            )
            .first()
        )

        if card:
            return card

        # Try with partial set name match - escape the set_name for LIKE
        from sqlalchemy import bindparam

        escaped_set_name = set_name.replace("%", "\\%").replace("_", "\\_")
        card = (
            self.session.query(PokemonCard)
            .join(PokemonSet)
            .filter(
                and_(
                    func.lower(PokemonCard.name) == name.lower(),
                    PokemonSet.name.ilike(f"%{escaped_set_name}%"),
                    PokemonCard.number == number,
                )
            )
            .first()
        )

        return card

    def _find_fuzzy_matches(
        self, name: str, set_name: str, number: str
    ) -> List[Tuple[PokemonCard, float]]:
        """Find fuzzy matches with scores"""
        matches = []

        # Get potential matches by name - escape the name for LIKE
        first_name = name.split()[0] if name.split() else name
        escaped_name = first_name.replace("%", "\\%").replace("_", "\\_")
        potential_cards = (
            self.session.query(PokemonCard)
            .filter(PokemonCard.name.ilike(f"%{escaped_name}%"))
            .limit(50)
            .all()
        )

        for card in potential_cards:
            # Calculate match score
            name_score = fuzz.ratio(name.lower(), card.name.lower())
            set_score = fuzz.partial_ratio(set_name.lower(), card.set.name.lower())

            # Number matching
            number_score = (
                100
                if number == card.number
                else (80 if number.split("/")[0] == card.number.split("/")[0] else 0)
            )

            # Weight the scores
            total_score = (name_score * 0.5) + (set_score * 0.3) + (number_score * 0.2)

            if total_score > 70:
                matches.append((card, total_score))

        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:5]  # Return top 5 matches

    def _identify_variation(
        self, card: PokemonCard, ximilar_result: Dict[str, Any]
    ) -> Optional[CardVariation]:
        """Identify specific card variation"""
        # Check for variation indicators
        is_reverse = any(term in str(ximilar_result).lower() for term in ["reverse", "rev holo"])
        is_first_ed = any(
            term in str(ximilar_result).lower() for term in ["1st edition", "first edition"]
        )
        is_stamped = any(
            term in str(ximilar_result).lower() for term in ["stamped", "staff", "league"]
        )

        # Find matching variation
        variations = card.variations

        for var in variations:
            if (
                var.is_reverse_holo == is_reverse
                and var.is_first_edition == is_first_ed
                and var.is_stamped == is_stamped
            ):
                return var

        # Return default variation if exists
        return next((v for v in variations if v.variation_type == "normal"), None)

    def _run_validation_rules(self, ximilar_result: Dict[str, Any]) -> List[str]:
        """Run active validation rules"""
        issues = []

        rules = (
            self.session.query(ValidationRule)
            .filter_by(is_active=True)
            .order_by(ValidationRule.priority.desc())
            .all()
        )

        for rule in rules:
            if self._check_rule(rule, ximilar_result):
                issues.append(rule.description or rule.name)

        return issues

    def _check_rule(self, rule: ValidationRule, ximilar_result: Dict[str, Any]) -> bool:
        """Check if a validation rule is triggered"""
        config = rule.rule_config
        rule_type = config.get("type")

        if rule_type == "era_mismatch":
            return self._check_era_mismatch_rule(config, ximilar_result)
        elif rule_type == "set_size_mismatch":
            return self._check_set_size_rule(config, ximilar_result)
        elif rule_type == "rarity_mismatch":
            return self._check_rarity_rule(config, ximilar_result)

        return False

    def _check_era_mismatch_rule(self, config: Dict, ximilar_result: Dict) -> bool:
        """Check for era mismatches"""
        card_patterns = config.get("conditions", {}).get("card_patterns", [])
        invalid_series = config.get("conditions", {}).get("invalid_series", [])

        name = ximilar_result.get("name", "").lower()
        set_name = ximilar_result.get("set_name", "").lower()

        # Check if card has modern pattern
        has_pattern = any(pattern.lower() in name for pattern in card_patterns)

        # Check if in old series
        in_old_series = any(series.lower() in set_name for series in invalid_series)

        return has_pattern and in_old_series

    def _check_set_size_rule(self, config: Dict, ximilar_result: Dict) -> bool:
        """Check for set size mismatches"""
        number = ximilar_result.get("number", "")
        if "/" not in number:
            return False

        try:
            card_num, set_total = number.split("/")
            set_total = int(set_total)

            # Look up actual set size - escape set_name for LIKE
            set_name = ximilar_result.get("set_name", "")
            escaped_set_name = set_name.replace("%", "\\%").replace("_", "\\_")
            actual_set = (
                self.session.query(PokemonSet)
                .filter(PokemonSet.name.ilike(f"%{escaped_set_name}%"))
                .first()
            )

            if actual_set and actual_set.printed_total:
                # Allow for secret rares (up to 50 beyond printed total)
                if (
                    set_total != actual_set.printed_total
                    and abs(set_total - actual_set.printed_total) > 50
                ):
                    return True
        except:
            pass

        return False

    def _check_rarity_rule(self, config: Dict, ximilar_result: Dict) -> bool:
        """Check for rarity mismatches"""
        # This would check if rarity makes sense for the card
        # e.g., Energy cards shouldn't be "Ultra Rare"
        return False

    def _validate_era(self, name: str, set_name: str) -> List[str]:
        """Validate card era consistency"""
        issues = []
        name_lower = name.lower()
        set_lower = set_name.lower()

        # Modern card types
        modern_only = {
            "v": ["sword", "shield", "scarlet", "violet"],
            "vmax": ["sword", "shield"],
            "vstar": ["sword", "shield", "scarlet", "violet"],
            "ex": ["scarlet", "violet"],  # Modern ex, not old ex
        }

        # Old card types
        old_only = {
            "lv.x": ["diamond", "pearl", "platinum", "heartgold", "soulsilver"],
            "prime": ["heartgold", "soulsilver"],
            "legend": ["heartgold", "soulsilver"],
            "break": ["xy", "breakpoint", "breakthrough", "breakthrough"],
        }

        # Check modern types in old sets
        for card_type, valid_eras in modern_only.items():
            if f" {card_type}" in name_lower or name_lower.endswith(card_type):
                if not any(era in set_lower for era in valid_eras):
                    issues.append(f"{card_type.upper()} cards don't exist in {set_name}")

        # Check old types in modern sets
        for card_type, valid_eras in old_only.items():
            if card_type in name_lower:
                modern_sets = ["sword", "shield", "scarlet", "violet"]
                if any(modern in set_lower for modern in modern_sets):
                    issues.append(f"{card_type.upper()} cards don't exist in modern sets")

        return issues

    def save_correction(
        self,
        ximilar_result: Dict[str, Any],
        correct_card: PokemonCard,
        correct_variation: Optional[CardVariation] = None,
        verified: bool = False,
    ):
        """Save a correction for future use"""
        correction = XimilarCorrection(
            ximilar_result=ximilar_result,
            correct_card_id=correct_card.id,
            correct_variation_id=correct_variation.id if correct_variation else None,
            confidence_threshold=ximilar_result.get("confidence", 1.0),
            verified=verified,
        )

        self.session.add(correction)
        self.session.commit()

        # Update cache
        key = self._make_correction_key(ximilar_result)
        self.correction_cache[key] = correction

        logger.info(f"Saved correction: {ximilar_result.get('name')} -> {correct_card.name}")

    def validate_and_correct(self, card_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate card data and attach database objects for accurate title generation

        Args:
            card_data: Dictionary containing card information from Ximilar

        Returns:
            Updated card_data with database objects attached
        """
        # Validate the Ximilar result
        validation_result = self.validate_card(card_data)

        # Attach database objects to card data for title generation
        if validation_result.get("correct_card"):
            card_data["database_card"] = validation_result["correct_card"]

        if validation_result.get("correct_variation"):
            card_data["database_variation"] = validation_result["correct_variation"]

        # Update confidence if validation suggests changes
        if validation_result.get("confidence_adjustment") != 1.0:
            original_confidence = card_data.get("confidence", 1.0)
            card_data["confidence"] = (
                original_confidence * validation_result["confidence_adjustment"]
            )

        # Add validation notes for debugging
        if validation_result.get("validation_notes"):
            card_data["validation_notes"] = validation_result["validation_notes"]

        # If validation suggests a correction, apply it
        if validation_result.get("suggested_correction"):
            correction = validation_result["suggested_correction"]
            logger.info(
                f"Applying suggested correction: {card_data.get('name')} -> {correction.get('name')}"
            )
            card_data.update(correction)

        return card_data
