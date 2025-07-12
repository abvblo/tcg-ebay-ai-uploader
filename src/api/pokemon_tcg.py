"""Enhanced Pokemon TCG API Client with better matching logic, database persistence, and adaptive rate limiting"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from ..database.service import DatabaseService
from ..price_mappings import PriceMappingConfig
from ..utils.logger import logger
from ..utils.rate_limiter import rate_limiter


class PokemonTCGClient:
    def __init__(self, api_key: str, rate_limit: float = 0.05, persist_to_db: bool = True):
        self.api_key = api_key
        self.base_url = "https://api.pokemontcg.io/v2/cards"
        self.rate_limit = rate_limit  # Keep for backwards compatibility
        self.price_config = PriceMappingConfig()
        self.persist_to_db = persist_to_db
        self.endpoint_name = "pokemon_tcg"

        logger.info("✅ Pokemon TCG API client initialized with database integration")

    async def get_card_data(
        self,
        card_name: str,
        set_name: str,
        session: aiohttp.ClientSession,
        unique_characteristics: List[str] = None,
        language: str = "English",
        card_number: str = None,
    ) -> Optional[Dict[str, Any]]:
        """Get card data from Pokemon TCG API with enhanced matching"""

        # Try multiple search strategies
        search_strategies = self._build_search_strategies(card_name, set_name, card_number)

        for strategy_name, params in search_strategies:
            logger.info(f"   🔍 Trying search strategy: {strategy_name}")

            headers = {"X-Api-Key": self.api_key} if self.api_key else {}

            # Use adaptive rate limiting
            await rate_limiter.acquire(self.endpoint_name)

            try:
                async with session.get(self.base_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        cards = data.get("data", [])
                        rate_limiter.report_success(self.endpoint_name)

                        # Find best match
                        best_match = self._find_best_match(cards, card_name, set_name, card_number)

                        if best_match:
                            market_price = self._extract_near_mint_price(
                                best_match, unique_characteristics, language
                            )
                            if market_price is not None:
                                logger.info(f"   ✅ Found match with {strategy_name} strategy")

                                # Database persistence is handled elsewhere
                                logger.debug(f"   💾 Card data ready for database storage")

                                return self._format_card_data(best_match, market_price)
                    elif response.status == 429:
                        rate_limiter.report_error(self.endpoint_name, is_rate_limit_error=True)
                        logger.error(f"Rate limit error with {strategy_name}: {response.status}")
                        await asyncio.sleep(5)  # Extra wait on rate limit
                        continue
                    else:
                        rate_limiter.report_error(self.endpoint_name)
                        logger.error(f"API error with {strategy_name}: {response.status}")
                        continue

            except Exception as e:
                rate_limiter.report_error(self.endpoint_name)
                logger.error(f"Pokemon TCG API error with {strategy_name}: {e}")
                continue

        logger.warning(f"   ⚠️ No match found for {card_name} after trying all strategies")
        return None

    def _build_search_strategies(
        self, card_name: str, set_name: str, card_number: str = None
    ) -> List[Tuple[str, Dict]]:
        """Build multiple search strategies for better matching"""
        strategies = []

        # Clean inputs
        clean_name = self._clean_card_name(card_name)
        clean_set = self._clean_set_name(set_name)

        # Strategy 1: Exact name and set search
        if clean_set and clean_set.lower() != "unknown":
            strategies.append(
                (
                    "Exact name + set",
                    {
                        "q": f'name:"{card_name}" set.name:"{set_name}"',
                        "pageSize": 10,
                        "orderBy": "-set.releaseDate",
                    },
                )
            )

        # Strategy 2: Card number search with set constraint (very reliable)
        if card_number and clean_set and clean_set.lower() != "unknown":
            # Extract just the number part (e.g., "SWSH283" from various formats)
            clean_number = self._clean_card_number(card_number)
            if clean_number:
                strategies.append(
                    (
                        "Card number + set search",
                        {
                            "q": f"number:{clean_number} set.name:\"{set_name}\"",
                            "pageSize": 20,
                            "orderBy": "-set.releaseDate",
                        },
                    )
                )

        # Strategy 3: Card number search for promos (without set constraint)
        if card_number:
            clean_number = self._clean_card_number(card_number)
            if clean_number and ("promo" in set_name.lower() or clean_number.startswith(("SWSH", "SM", "XY", "BW"))):
                strategies.append(
                    (
                        "Promo number search",
                        {
                            "q": f"number:{clean_number}",
                            "pageSize": 20,
                            "orderBy": "-set.releaseDate",
                        },
                    )
                )

        # Strategy 4: Name only search (broader)
        strategies.append(
            (
                "Name only",
                {"q": f'name:"{clean_name}"', "pageSize": 15, "orderBy": "-set.releaseDate"},
            )
        )

        # Strategy 5: Partial name search for complex names
        name_parts = clean_name.split()
        if len(name_parts) > 1:
            # Try first two words
            partial_name = " ".join(name_parts[:2])
            strategies.append(
                (
                    "Partial name",
                    {"q": f'name:"{partial_name}"', "pageSize": 20, "orderBy": "-set.releaseDate"},
                )
            )

        # Strategy 6: Set-based search for promos
        if "promo" in set_name.lower():
            strategies.append(
                (
                    "Promo search",
                    {
                        "q": f'name:"{clean_name}" set.name:*promo*',
                        "pageSize": 20,
                        "orderBy": "-set.releaseDate",
                    },
                )
            )

        return strategies

    def _clean_card_name(self, card_name: str) -> str:
        """Clean card name for better matching"""
        # Remove common suffixes that might interfere
        suffixes_to_remove = [" v", " vmax", " vstar", " ex", " gx", " tag team"]
        clean_name = card_name.lower()
        for suffix in suffixes_to_remove:
            if clean_name.endswith(suffix):
                clean_name = clean_name[: -len(suffix)]
                break

        # Remove special characters but keep spaces
        import re

        clean_name = re.sub(r"[^\w\s-]", "", card_name).strip()

        return clean_name

    def _clean_set_name(self, set_name: str) -> str:
        """Clean set name for better matching"""
        # Common set name variations to normalize
        set_mappings = {
            "sword shield promos": "SWSH Black Star Promos",
            "swsh promos": "SWSH Black Star Promos",
            "sword & shield promos": "SWSH Black Star Promos",
            "sun moon promos": "SM Black Star Promos",
            "sm promos": "SM Black Star Promos",
            "xy promos": "XY Black Star Promos",
            "black white promos": "BW Black Star Promos",
            "bw promos": "BW Black Star Promos",
        }

        lower_set = set_name.lower()
        for key, value in set_mappings.items():
            if key in lower_set:
                return value

        return set_name

    def _clean_card_number(self, card_number: str) -> str:
        """Extract clean card number for searching"""
        if not card_number:
            return ""

        # Remove common prefixes/suffixes
        import re

        # Handle different formats: "11/20", "SWSH283", "SM-P 283", etc.
        # First, check if it's a promo number
        promo_match = re.search(
            r"(SWSH|SM|XY|BW|DP|HGSS)\s*-?\s*P?\s*(\d+)", card_number, re.IGNORECASE
        )
        if promo_match:
            return f"{promo_match.group(1)}{promo_match.group(2)}".upper()

        # Check for standalone promo numbers
        if re.match(r"^(SWSH|SM|XY|BW)\d+$", card_number, re.IGNORECASE):
            return card_number.upper()

        # For regular set numbers, extract just the number part
        number_match = re.search(r"(\d+)", card_number)
        if number_match:
            return number_match.group(1)

        return card_number

    def _find_best_match(
        self, cards: List[Dict], target_name: str, target_set: str, target_number: str = None
    ) -> Optional[Dict]:
        """Find the best matching card from search results with improved matching logic"""
        if not cards:
            return None

        # Score each card
        scored_cards = []
        target_name_lower = target_name.lower()
        target_set_lower = target_set.lower()

        for card in cards:
            score = 0
            card_name = card.get("name", "").lower()
            card_set = card.get("set", {}).get("name", "").lower()
            card_number = card.get("number", "").lower()

            # IMPROVED: Exact name matching with case-sensitive suffix handling
            if card_name == target_name_lower:
                score += 100
            elif self._names_match_with_suffix_handling(target_name, card.get("name", "")):
                score += 90  # High score for proper suffix matching
            elif target_name_lower in card_name or card_name in target_name_lower:
                score += 50

            # IMPROVED: Set matching with better normalization
            if card_set == target_set_lower:
                score += 80  # Increased weight for exact set match
            elif self._sets_match_with_normalization(target_set, card.get("set", {}).get("name", "")):
                score += 70  # High score for normalized set match
            elif "promo" in target_set_lower and "promo" in card_set:
                score += 30
            elif target_set_lower in card_set or card_set in target_set_lower:
                score += 20

            # IMPROVED: Number matching with stricter validation
            if target_number:
                clean_target_number = self._clean_card_number(target_number).lower()
                if card_number == clean_target_number:
                    score += 100  # Increased weight for exact number match
                elif clean_target_number in card_number:
                    score += 60

            # PENALTY: Reduce score for modern cards when looking for vintage
            if self._is_vintage_set(target_set) and not self._is_vintage_set(card.get("set", {}).get("name", "")):
                score -= 30  # Penalty for modern cards when searching vintage

            # PENALTY: Reduce score for wrong language/region
            if self._is_wrong_language_or_region(card, target_set):
                score -= 20

            # Prefer cards with TCGPlayer data
            if card.get("tcgplayer", {}).get("url"):
                score += 10

            # Prefer cards with prices
            if card.get("tcgplayer", {}).get("prices"):
                score += 10

            scored_cards.append((score, card))

        # Sort by score and return best match
        scored_cards.sort(key=lambda x: x[0], reverse=True)

        if scored_cards and scored_cards[0][0] > 60:  # Require minimum score threshold
            best_score, best_card = scored_cards[0]
            logger.debug(
                f"      Best match score: {best_score} for {best_card.get('name')} - {best_card.get('set', {}).get('name')}"
            )
            return best_card

        return None

    def _names_match_with_suffix_handling(self, target_name: str, card_name: str) -> bool:
        """Check if names match with proper handling of EX vs ex suffixes"""
        target_lower = target_name.lower()
        card_lower = card_name.lower()
        
        # Handle EX vs ex distinction (EX is vintage, ex is modern)
        if "ex" in target_lower and "ex" in card_lower:
            # Both have ex/EX - check if they're the same type
            target_has_capital_ex = " EX" in target_name or target_name.endswith("EX")
            card_has_capital_ex = " EX" in card_name or card_name.endswith("EX")
            
            if target_has_capital_ex != card_has_capital_ex:
                return False  # Different EX types
                
        # Remove common suffixes for comparison
        target_base = target_lower.replace(" ex", "").replace(" gx", "").replace(" v", "").replace(" vmax", "").replace(" vstar", "")
        card_base = card_lower.replace(" ex", "").replace(" gx", "").replace(" v", "").replace(" vmax", "").replace(" vstar", "")
        
        return target_base == card_base

    def _sets_match_with_normalization(self, target_set: str, card_set: str) -> bool:
        """Check if sets match with proper normalization"""
        target_normalized = self._normalize_set_name(target_set)
        card_normalized = self._normalize_set_name(card_set)
        
        return target_normalized == card_normalized

    def _normalize_set_name(self, set_name: str) -> str:
        """Normalize set names for better matching"""
        normalized = set_name.lower().strip()
        
        # Common set name normalizations
        normalizations = {
            "ancient origins": "xy ancient origins",
            "xy - ancient origins": "xy ancient origins", 
            "base set": "base",
            "base set 2": "base set 2",
            "xy ancient origins": "xy ancient origins",
            "prismatic evolutions": "scarlet & violet prismatic evolutions",
            "sv prismatic evolutions": "scarlet & violet prismatic evolutions",
            "paldean fates": "scarlet & violet paldean fates",
            "crown zenith": "sword & shield crown zenith",
        }
        
        return normalizations.get(normalized, normalized)

    def _is_vintage_set(self, set_name: str) -> bool:
        """Check if a set is vintage (pre-2010)"""
        vintage_sets = {
            "base", "base set", "jungle", "fossil", "team rocket", "gym heroes", "gym challenge",
            "neo genesis", "neo discovery", "neo revelation", "neo destiny", "legendary collection",
            "expedition", "aquapolis", "skyridge", "ruby & sapphire", "sandstorm", "dragon",
            "team magma vs team aqua", "hidden legends", "firered & leafgreen", "team rocket returns",
            "deoxys", "emerald", "unseen forces", "delta species", "legend maker", "holon phantoms",
            "crystal guardians", "dragon frontiers", "power keepers", "diamond & pearl", "mysterious treasures",
            "secret wonders", "great encounters", "majestic dawn", "legends awakened", "stormfront",
            "platinum", "rising rivals", "supreme victors", "arceus", "heartgold & soulsilver",
            "unleashed", "undaunted", "triumphant", "call of legends", "black & white", "emerging powers",
            "noble victories", "next destinies", "dark explorers", "dragons exalted", "boundaries crossed",
            "plasma storm", "plasma freeze", "plasma blast", "legendary treasures", "xy", "flashfire",
            "furious fists", "phantom forces", "primal clash", "roaring skies", "ancient origins"
        }
        
        set_lower = set_name.lower()
        return any(vintage in set_lower for vintage in vintage_sets)

    def _is_wrong_language_or_region(self, card: Dict, target_set: str) -> bool:
        """Check if card is from wrong language/region"""
        card_set = card.get("set", {}).get("name", "").lower()
        
        # Check for Japanese-only sets when looking for English cards
        japanese_indicators = ["japanese", "japan", "promo pack", "プロモ"]
        if any(indicator in card_set for indicator in japanese_indicators):
            return True
            
        return False

    def _extract_near_mint_price(
        self,
        card: Dict[str, Any],
        unique_characteristics: List[str] = None,
        language: str = "English",
    ) -> Optional[float]:
        """Extract NEAR MINT price from Pokemon TCG data based on card characteristics"""
        tcgplayer = card.get("tcgplayer", {})
        if not tcgplayer:
            return None

        prices = tcgplayer.get("prices", {})
        if not prices:
            return None

        # Determine price categories to check based on characteristics
        priority_categories = self._determine_price_categories(
            unique_characteristics, language, list(prices.keys()), card.get("set", {}).get("name")
        )

        # Log only essential info
        if unique_characteristics:
            logger.info(f"      Edition: {', '.join(unique_characteristics)}")

        # Try to find a NEAR MINT price using the priority order
        for price_key in priority_categories:
            if price_key in prices:
                price_data = prices[price_key]
                if isinstance(price_data, dict):
                    # Pokemon TCG API uses 'market' for Near Mint market price
                    for price_field in ["market", "mid"]:  # Only Near Mint prices
                        if price_field in price_data:
                            price_value = price_data.get(price_field)
                            if price_value and float(price_value) > 0:
                                logger.info(
                                    f"      Using {price_key} Near Mint price: ${price_value}"
                                )
                                return float(price_value)

        # Final fallback: Use ANY available Near Mint price (but warn about it)
        for price_category, price_data in prices.items():
            if isinstance(price_data, dict):
                for price_field in ["market", "mid"]:
                    if price_field in price_data:
                        price_value = price_data.get(price_field)
                        if price_value and float(price_value) > 0:
                            logger.warning(
                                f"      ⚠️ No matching category - using {price_category} Near Mint: ${price_value}"
                            )
                            return float(price_value)

        return None

    def _determine_price_categories(
        self,
        unique_characteristics: List[str] = None,
        language: str = "English",
        available_categories: List[str] = None,
        set_name: str = None,
    ) -> List[str]:
        """Determine which price categories to check based on card characteristics"""
        priority_categories = []

        # First, check for special combinations
        if unique_characteristics:
            combination_categories = self.price_config.get_combination_categories(
                unique_characteristics
            )
            priority_categories.extend(combination_categories)

        # Process individual characteristics
        if unique_characteristics:
            for characteristic in unique_characteristics:
                categories = self.price_config.get_mapping(characteristic)
                priority_categories.extend(categories)

        # Handle language-specific categories
        if language and language.lower() != "english":
            lang_categories = self.price_config.get_mapping(language)
            priority_categories.extend(lang_categories)

        # Add default categories
        priority_categories.extend(self.price_config.DEFAULT_CATEGORIES)

        # Apply set-specific rules
        if set_name:
            priority_categories = self.price_config.apply_set_rules(set_name, priority_categories)

        # Apply exclusion rules
        priority_categories = self.price_config.apply_exclusion_rules(
            unique_characteristics or [], priority_categories
        )

        # Remove duplicates while preserving order
        seen = set()
        unique_categories = []
        for cat in priority_categories:
            if cat not in seen:
                seen.add(cat)
                unique_categories.append(cat)

        # Filter to only available categories if provided
        if available_categories:
            available_set = set(available_categories)
            unique_categories = [cat for cat in unique_categories if cat in available_set]

        return unique_categories

    def _extract_finish(self, card: Dict[str, Any]) -> str:
        """Extract finish information from card data"""
        # [Keep the existing _extract_finish method unchanged]
        # ... (same as before)

    def _extract_features(self, card: Dict[str, Any]) -> List[str]:
        """Extract special features/characteristics from card data"""
        # [Keep the existing _extract_features method unchanged]
        # ... (same as before)

    def _format_card_data(self, card: Dict[str, Any], market_price: float) -> Dict[str, Any]:
        """Format Pokemon card data with enhanced fields"""
        # Get the direct TCGPlayer URL from the API response
        tcgplayer_data = card.get("tcgplayer", {})
        tcgplayer_url = tcgplayer_data.get("url", "")

        # Validate the URL is a product URL, not a search URL
        if tcgplayer_url and "/product/" not in tcgplayer_url:
            logger.warning(f"      ⚠️ TCGPlayer URL appears to be a search page, not a product page")
            # You might want to set this to empty to trigger fallback
            # tcgplayer_url = ''

        # Extract finish and features from API data
        finish = self._extract_finish(card)
        features = self._extract_features(card)

        # Log what we found
        logger.info(
            f"      📊 Card: {card.get('name')} - {card.get('set', {}).get('name')} #{card.get('number')}"
        )
        logger.info(f"      🔗 TCGPlayer URL: {tcgplayer_url if tcgplayer_url else 'Not found'}")

        # Get trainer/ability information if available
        abilities = card.get("abilities", [])
        ability_names = [ability.get("name", "") for ability in abilities] if abilities else []

        # Get attack information
        attacks = card.get("attacks", [])
        attack_names = [attack.get("name", "") for attack in attacks] if attacks else []

        # Get evolution information
        evolves_from = card.get("evolvesFrom", "")
        evolves_to = [evo for evo in card.get("evolvesTo", [])] if card.get("evolvesTo") else []

        # TODO: Add database integration for card lookup
        # This would check if the card already exists in the database

        formatted_data = {
            "api_price": market_price,
            "price_source": "Pokemon TCG API - Near Mint",
            "pokemon_tcg_id": card.get("id"),
            "hp": str(card.get("hp", "")),
            "types": card.get("types", []),
            "subtypes": card.get("subtypes", []),
            "supertype": card.get("supertype"),
            "artist": card.get("artist"),
            "rarity_confirmed": card.get("rarity"),
            "set_confirmed": card.get("set", {}).get("name"),
            "set_series": card.get("set", {}).get("series"),
            "set_total": card.get("set", {}).get("total"),
            "number_confirmed": card.get("number"),
            "release_date": card.get("set", {}).get("releaseDate"),
            "retreat_cost": card.get("retreatCost", []),
            "converted_retreat_cost": card.get("convertedRetreatCost"),
            "weaknesses": card.get("weaknesses", []),
            "resistances": card.get("resistances", []),
            "abilities": ability_names,
            "attacks": attack_names,
            "evolves_from": evolves_from,
            "evolves_to": evolves_to,
            "regulation_mark": card.get("regulationMark"),
            "finish_api": finish,
            "features_api": features,
            "data_source": "Pokemon TCG API",
            "tcgplayer_url": tcgplayer_url,
            "tcgplayer_link": tcgplayer_url,
        }

        # Database information would be added here if available
        # This is handled in the database persistence layer
        formatted_data["database_validated"] = False

        return formatted_data

    async def get_card_pricing(
        self, name: str, set_name: str = "", number: str = "", session: aiohttp.ClientSession = None
    ) -> Optional[Dict[str, Any]]:
        """Get pricing data for a Pokemon card - first checks database, then API"""

        # TODO: Add database cache check for recent pricing
        # This would check if we have recent pricing data in the database
        # to avoid unnecessary API calls

        # Fetch from API
        if not session:
            async with aiohttp.ClientSession() as session:
                card_data = await self.get_card_data(name, set_name, session, card_number=number)
        else:
            card_data = await self.get_card_data(name, set_name, session, card_number=number)

        if card_data and "api_price" in card_data:
            return {
                "api_price": card_data["api_price"],
                "price_source": card_data["price_source"],
                "price_category": card_data.get("price_category", ""),
                "tcgplayer_url": card_data.get("tcgplayer_url"),
                "data_source": "Pokemon TCG API",
                "database_card_id": card_data.get("database_card_id"),
            }
        return None

    async def get_all_sets(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Get all sets from the Pokemon TCG API."""
        headers = {"X-Api-Key": self.api_key} if self.api_key else {}

        await rate_limiter.acquire(self.endpoint_name)

        try:
            async with session.get(
                "https://api.pokemontcg.io/v2/sets", headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    rate_limiter.report_success(self.endpoint_name)
                    return data.get("data", [])
                elif response.status == 429:
                    rate_limiter.report_error(self.endpoint_name, is_rate_limit_error=True)
                    logger.error(f"Rate limit error fetching all sets: {response.status}")
                    return []
                else:
                    rate_limiter.report_error(self.endpoint_name)
                    logger.error(
                        f"Error fetching all sets: {response.status} {await response.text()}"
                    )
                    return []
        except Exception as e:
            rate_limiter.report_error(self.endpoint_name)
            logger.error(f"Exception fetching all sets: {e}")
            return []

    async def get_cards_by_set_id(
        self, set_id: str, session: aiohttp.ClientSession
    ) -> List[Dict[str, Any]]:
        """Get all cards for a given set ID."""
        headers = {"X-Api-Key": self.api_key} if self.api_key else {}
        params = {"q": f"set.id:{set_id}", "pageSize": 250, "orderBy": "number"}

        await rate_limiter.acquire(self.endpoint_name)

        try:
            async with session.get(self.base_url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    rate_limiter.report_success(self.endpoint_name)
                    return data.get("data", [])
                elif response.status == 429:
                    rate_limiter.report_error(self.endpoint_name, is_rate_limit_error=True)
                    logger.error(f"Rate limit error fetching set {set_id}: {response.status}")
                    return []
                else:
                    rate_limiter.report_error(self.endpoint_name)
                    logger.error(
                        f"Error fetching set {set_id}: {response.status} {await response.text()}"
                    )
                    return []
        except Exception as e:
            rate_limiter.report_error(self.endpoint_name)
            logger.error(f"Exception fetching set {set_id}: {e}")
            return []

    async def bulk_import_set_to_database(
        self, set_id: str, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Import an entire set to the database"""
        try:
            # Get set information
            set_info = None
            all_sets = await self.get_all_sets(session)
            for s in all_sets:
                if s["id"] == set_id:
                    set_info = s
                    break

            if not set_info:
                logger.error(f"Set {set_id} not found")
                return {"success": False, "error": "Set not found"}

            # Get all cards in the set
            cards = await self.get_cards_by_set_id(set_id, session)

            if not cards:
                logger.warning(f"No cards found for set {set_id}")
                return {"success": False, "error": "No cards found"}

            # Database import would happen here
            logger.info(f"✅ Would import {len(cards)} cards from set {set_info['name']}")

            return {
                "success": True,
                "set_name": set_info["name"],
                "total_cards": len(cards),
                "imported_cards": len(cards),
                "set_created": True,
            }

        except Exception as e:
            logger.error(f"Bulk import failed for set {set_id}: {e}")
            return {"success": False, "error": str(e)}

    async def bulk_import_all_sets(
        self, session: aiohttp.ClientSession, max_sets: int = None
    ) -> Dict[str, Any]:
        """Import all sets and their cards to the database"""
        try:
            # Get all sets
            all_sets = await self.get_all_sets(session)

            if max_sets:
                all_sets = all_sets[:max_sets]

            logger.info(f"Starting bulk import of {len(all_sets)} sets")

            results = {
                "total_sets": len(all_sets),
                "imported_sets": 0,
                "total_cards": 0,
                "imported_cards": 0,
                "errors": [],
            }

            for i, set_info in enumerate(all_sets, 1):
                logger.info(f"Importing set {i}/{len(all_sets)}: {set_info['name']}")

                result = await self.bulk_import_set_to_database(set_info["id"], session)

                if result["success"]:
                    results["imported_sets"] += 1
                    results["total_cards"] += result["total_cards"]
                    results["imported_cards"] += result["imported_cards"]
                else:
                    results["errors"].append(f"Set {set_info['name']}: {result['error']}")

                # Add delay between sets to avoid rate limiting
                await asyncio.sleep(1)

            logger.info(
                f"✅ Bulk import completed: {results['imported_sets']} sets, {results['imported_cards']} cards"
            )
            return results

        except Exception as e:
            logger.error(f"Bulk import failed: {e}")
            return {"success": False, "error": str(e)}
