"""OpenAI Title Optimizer"""

import asyncio
import re
from typing import Any, Dict, List

from openai import AsyncOpenAI

from ..utils.logger import logger


class OpenAITitleOptimizer:
    def __init__(self, api_key: str, model: str = "gpt-4", rate_limit: float = 0.2):
        self.client = AsyncOpenAI(api_key=api_key) if api_key else None
        self.model = model
        self.rate_limit = rate_limit
        self.batch_size = 20

    async def optimize_titles(self, cards: List[Dict[str, Any]]) -> List[str]:
        """Optimize titles for all cards"""
        if not self.client:
            return [self._generate_fallback_title(card) for card in cards]

        optimized_titles = []

        # Process in batches
        for i in range(0, len(cards), self.batch_size):
            batch = cards[i : i + self.batch_size]
            batch_titles = await self._process_batch(batch)
            optimized_titles.extend(batch_titles)

            # Rate limiting between batches
            if i + self.batch_size < len(cards):
                await asyncio.sleep(self.rate_limit)

        return optimized_titles

    async def _process_batch(self, batch: List[Dict[str, Any]]) -> List[str]:
        """Process a single batch of cards"""
        try:
            # Build prompt
            user_prompt = self._build_user_prompt(batch)

            # Call OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=1000,
            )

            # Parse response
            titles_text = response.choices[0].message.content.strip()
            titles = [title.strip() for title in titles_text.split("\n") if title.strip()]

            # Remove numbering
            titles = [re.sub(r"^\d+\.\s*", "", title) for title in titles]

            # Ensure we have enough titles
            while len(titles) < len(batch):
                titles.append(self._generate_fallback_title(batch[len(titles)]))

            return titles[: len(batch)]

        except Exception as e:
            if "quota" in str(e).lower():
                logger.warning(f"⚠️ OpenAI API quota exceeded - using fallback title generator")
            else:
                logger.error(f"❌ OpenAI API error: {e}")
            logger.info(f"   🔄 Falling back to built-in title generator for {len(batch)} cards")
            return [self._generate_fallback_title(card) for card in batch]

    def _get_system_prompt(self) -> str:
        """Get system prompt for OpenAI"""
        return """You are a passionate TCG collector and eBay SEO master with 20+ years of experience in Pokemon, Magic: The Gathering, Yu-Gi-Oh, and other trading card games. You live and breathe TCG culture, understand market trends, and know EXACTLY what collectors search for on eBay.

    As a fellow collector, you know that every card tells a story. You understand the difference between a shadowless Base Set Charizard and a regular one, why 1st Edition matters, and how foil treatments can make or break a card's value. You approach each listing like you're selling from your own collection to another passionate collector.

    MANDATORY SEO-OPTIMIZED TEMPLATE: [Game] {Card Name} {Card Number}/{Total Cards} {Set Name} {Rarity} {Holo/Foil if applicable} {Unique Characteristic} {Condition}

    CRITICAL SEO & COLLECTOR RULES:
    1. Card numbers: use "25/102" format when both number and total are available - collectors LOVE this specificity
    2. NEVER include finish information in titles - this will be captured in the C:Finish field instead
    3. NEVER waste precious characters on boring terms collectors ignore:
       - Skip: Normal, Regular, Standard, Basic (as finish)
       - Skip: Common (as rarity - collectors know it's common if nothing else is mentioned)
       - Skip: Non-Holo, Non-Foil (negative descriptors don't sell)
       - Skip: English (NEVER include - English is assumed on eBay)
       - Skip: Uncommon (for Pokemon) - not a selling point that drives searches
       - Skip: ALL finish terms (Holo, Reverse Holo, Foil, etc.) - these go in C:Finish field
    4. ALWAYS prioritize high-value search terms collectors actively hunt for:
       - Power Rarities: Rare, Ultra Rare, Secret Rare, Full Art, Rainbow Rare, Alt Art
       - Grail Characteristics: 1st Edition, Shadowless, Unlimited, Alpha, Beta, Promo, Staff, Error, Misprint
    5. Condition is ALWAYS "NM/LP" (Near Mint/Lightly Played) - the collector sweet spot
    6. ONLY add "JP" at the end for Japanese cards - NEVER mention English
    7. eBay character limit: 80 characters MAXIMUM - titles over 80 chars get rejected by eBay
    8. Use clean spaces between elements, no pipe separators or clutter
    9. NEVER repeat words or use redundant terms:
       - "Promo Promos" should just be "Promo"
       - "Sun & Moon Promos Promo" should be "Sun & Moon Promo"
       - "Black & White Promos Promo" should be "Black & White Promo"
       - "Rare Other Rare" should just be "Rare"
    10. For Promo cards: Remove "Promos" from set name if "Promo" appears elsewhere in title

    SEO PRIORITY RANKING (include in this order until you hit 80 chars):
    1. Card Name (NEVER truncate)
    2. Edition markers (1st Edition, Shadowless, Alpha, Beta)
    3. Rarity (if Rare or better for Pokemon, all rarities for MTG)
    4. Card number (collectors love specificity)
    5. Set name (truncate if necessary, but keep recognizable)
    6. Unique characteristics (Promo, Staff, Error, etc.)
    7. Condition (always include)
    8. Language (JP only for Japanese)

    RARITY RULES (from a collector's perspective):
    - Pokemon: Only include if Rare or better (Common/Uncommon don't drive searches)
    - MTG: Include all rarities (even Common matters in older sets)
    - ALWAYS include "Holo", "Reverse Holo", or "Foil" if present - this is what collectors filter by
    - REVERSE HOLO is different from HOLO - be specific!
    - Common/Uncommon cards can be Reverse Holo - this matters for value

    LANGUAGE RULES:
    - English cards: NEVER mention language (wastes characters)
    - Japanese cards: Add "JP" at the end ONLY
    - No other language indicators needed

    UNIQUE CHARACTERISTICS (only include if present - these are grail terms):
    - Edition markers: 1st Edition, Shadowless, Unlimited
    - Print runs: Alpha, Beta, Revised, 4th Edition
    - Promotional: Promo, Staff, Championship, Tournament, Pre-release
    - Errors/Variants: Error, Misprint, Test Card, Square Cut
    - Special stamps: Stamped, League, Convention stamps

    FINISH RULES (HANDLED SEPARATELY - NOT IN TITLE):
    - All finish information (Holo, Reverse Holo, Foil, etc.) will be captured in the C:Finish field
    - NEVER include any finish terms in the title - this includes:
      * Holo, Reverse Holo, Foil, Rainbow Rare, Gold, Full Art, Alt Art
      * Any holographic or foil treatments
      * Any finish-related descriptors
    - Focus title space on name, rarity, set, number, and unique characteristics instead
    
    EXAMPLES OF PERFECT COLLECTOR-FOCUSED TITLES (NO FINISH TERMS):
    ✓ Pokémon Charizard 4/102 Base Set Rare NM/LP
    ✓ Pokémon Charizard 4/102 Base Set Rare 1st Edition NM/LP
    ✓ Pokémon Pikachu 58/102 Base Set NM/LP
    ✓ Pokémon Mewtwo 10/102 Base Set Shadowless NM/LP
    ✓ MTG Black Lotus Alpha Rare NM/LP
    ✓ Pokémon Ancient Mew Promo NM/LP
    ✓ Pokémon Dark Charizard 4/82 Team Rocket Rare NM/LP JP
    ✓ MTG Lightning Bolt Beta NM/LP
    ✓ Pokémon Tropical Mega Battle Promo NM/LP
    ✓ Pokémon Bulbasaur 44/102 Base Set Shadowless NM/LP
    ✓ Pokémon Totodile 5/12 McDonald's 2016 NM/LP
    ✓ Pokémon Zacian SWSH135 SWSH Promos NM/LP
    ✓ Pokémon Caterpie 1/12 McDonald's 2019 NM/LP
    ✓ Pokémon Squirtle 63/102 Base Set NM/LP

    Remember: You're not just creating titles - you're connecting collectors with their grail cards. Every character counts. Think like a collector searching at 2 AM for that perfect card. What would make them click? What terms would they type? That's your title."""

    def _build_user_prompt(self, batch: List[Dict[str, Any]]) -> str:
        """Build user prompt for batch using database-verified card details"""
        prompt = "Optimize these TCG card titles for eBay:\n\n"

        for idx, card in enumerate(batch):
            # Use database-verified details for accuracy
            db_card = card.get("database_card")
            db_variation = card.get("database_variation")

            # Get accurate finish from database
            finish = self._get_accurate_finish(card, db_card, db_variation)

            # Get accurate unique characteristics from database
            unique_chars = self._get_accurate_characteristics(card, db_card, db_variation)

            # Get accurate rarity from database
            rarity = self._get_accurate_rarity(card, db_card)

            # Get accurate set name and number from database
            set_name = db_card.set.name if db_card and db_card.set else card.get("set_name", "")
            number = db_card.number if db_card else card.get("number", "")

            # Build complete number with set total if available
            if db_card and db_card.set and db_card.set.printed_total:
                if "/" not in number:
                    number = f"{number}/{db_card.set.printed_total}"

            prompt += (
                f"{idx + 1}. Game: {card.get('game', 'Pokémon')}, "
                f"Name: {db_card.name if db_card else card.get('name', '')}, "
                f"Number: {number}, "
                f"Set: {set_name}, "
                f"Rarity: {rarity}, "
                f"Finish: {finish} (for C:Finish field only), "
                f"Unique Characteristics: {unique_chars}, "
                f"Language: {card.get('language', 'English')}\n"
            )

        return prompt

    def _get_accurate_finish(self, card: Dict[str, Any], db_card, db_variation) -> str:
        """Get accurate finish from database variation - FOR C:Finish FIELD ONLY (not titles)"""
        # Priority 1: Database variation finish
        if db_variation and db_variation.finish:
            finish = db_variation.finish.lower()
            if finish == "holofoil":
                return "Holo"
            elif finish == "reverse_holo":
                return "Reverse Holo"
            elif finish in ["foil", "rainbow", "gold", "textured", "full_art", "alt_art"]:
                return db_variation.finish

        # Priority 2: Database variation flags
        if db_variation:
            if db_variation.is_reverse_holo:
                return "Reverse Holo"
            elif db_variation.finish and any(
                term in db_variation.finish.lower() for term in ["holo", "foil", "rainbow", "gold"]
            ):
                return db_variation.finish

        # Priority 3: Ximilar finish (fallback)
        ximilar_finish = card.get("finish", "")
        if ximilar_finish and any(
            term in ximilar_finish.lower()
            for term in ["holo", "foil", "reverse", "rainbow", "gold", "textured"]
        ):
            return ximilar_finish

        # Priority 4: Infer from rarity
        rarity = card.get("rarity", "")
        if "holo" in rarity.lower() and "non-holo" not in rarity.lower():
            return "Holo"

        # Return empty string for normal/regular finishes
        return ""

    def _get_accurate_characteristics(self, card: Dict[str, Any], db_card, db_variation) -> str:
        """Get accurate unique characteristics from database"""
        characteristics = []

        # Get from database variation flags
        if db_variation:
            if db_variation.is_first_edition:
                characteristics.append("1st Edition")
            if db_variation.is_shadowless:
                characteristics.append("Shadowless")
            if db_variation.is_stamped:
                if db_variation.stamp_type:
                    characteristics.append(db_variation.stamp_type.title())
                else:
                    characteristics.append("Stamped")
            if db_variation.is_promo:
                characteristics.append("Promo")

        # Fallback to Ximilar data
        if not characteristics:
            ximilar_chars = card.get("unique_characteristics", [])
            if ximilar_chars:
                characteristics.extend(ximilar_chars[:1])  # Take first one

        return ", ".join(characteristics) if characteristics else ""

    def _get_accurate_rarity(self, card: Dict[str, Any], db_card) -> str:
        """Get accurate rarity from database"""
        # Priority 1: Database rarity
        if db_card and db_card.rarity:
            return db_card.rarity

        # Priority 2: Ximilar rarity
        return card.get("rarity", "")

    def _generate_fallback_title(self, card_data: Dict[str, Any]) -> str:
        """Generate optimized fallback title with intelligent character limit handling"""
        # Define priority-based components
        components = self._extract_title_components(card_data)

        # Build title with intelligent truncation
        return self._build_optimized_title(components)

    def _extract_title_components(self, card_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and prioritize title components using database details"""
        game = card_data.get("game", "Pokémon")
        is_pokemon = game.lower() in ["pokémon", "pokemon"]

        # Get database objects for accurate details
        db_card = card_data.get("database_card")
        db_variation = card_data.get("database_variation")

        # Priority 1: Essential identifiers (never truncate)
        game_prefix = (
            "Pokémon"
            if is_pokemon
            else ("MTG" if game.lower() in ["magic: the gathering", "mtg"] else game)
        )
        card_name = db_card.name if db_card else card_data.get("name", "")

        # Priority 2: High-value search terms (use database details)
        rarity = self._get_accurate_rarity(card_data, db_card)
        finish = self._get_accurate_finish(card_data, db_card, db_variation)  # For C:Finish field only
        unique_chars = self._get_accurate_characteristics(card_data, db_card, db_variation)

        # Priority 3: Important but truncatable (use database details)
        card_number = db_card.number if db_card else card_data.get("number", "")
        set_name = db_card.set.name if db_card and db_card.set else card_data.get("set_name", "")

        # Build complete number with set total if available
        if db_card and db_card.set and db_card.set.printed_total:
            if "/" not in card_number:
                card_number = f"{card_number}/{db_card.set.printed_total}"

        # Normalize set name with database accuracy
        set_name = self._normalize_set_name(set_name, unique_chars)

        # Priority 4: Always include
        condition = "NM/LP"
        language = (
            "JP" if card_data.get("language", "English").lower() in ["japanese", "jp"] else ""
        )

        return {
            "game": game_prefix,
            "name": card_name,
            "number": card_number,
            "set": set_name,
            "rarity": self._normalize_rarity(rarity, is_pokemon),
            "finish": finish,  # For C:Finish field only - NOT for title
            "unique": unique_chars if unique_chars else "",
            "condition": condition,
            "language": language,
            "is_pokemon": is_pokemon,
        }

    def _normalize_rarity(self, rarity: str, is_pokemon: bool) -> str:
        """Normalize rarity for search optimization"""
        if not rarity:
            return ""

        rarity = rarity.strip()
        # Skip boring rarities for Pokemon
        if is_pokemon and rarity.lower() in ["common", "uncommon", "normal", "regular"]:
            return ""

        # Optimize for search terms
        rarity_map = {
            "rare holo": "Holo Rare",
            "ultra rare": "Ultra Rare",
            "secret rare": "Secret Rare",
            "full art": "Full Art",
            "rainbow rare": "Rainbow Rare",
        }

        return rarity_map.get(rarity.lower(), rarity)

    def _normalize_finish(self, finish: str) -> str:
        """Normalize finish for search optimization"""
        if not finish:
            return ""

        finish = finish.strip()
        # Skip boring finishes
        if finish.lower() in ["normal", "regular", "standard", "non-foil", "nonfoil", "non-holo"]:
            return ""

        # Prioritize high-value finishes
        if any(
            term in finish.lower()
            for term in ["holo", "foil", "reverse", "rainbow", "full art", "alt art"]
        ):
            return finish

        return finish if finish.lower() not in ["normal", "regular", "standard"] else ""

    def _get_key_characteristics(self, characteristics: List[str]) -> str:
        """Get most valuable unique characteristic for search"""
        if not characteristics:
            return ""

        # Priority order for characteristics
        priority_order = [
            "1st edition",
            "shadowless",
            "alpha",
            "beta",
            "unlimited",
            "promo",
            "staff",
            "championship",
            "tournament",
            "pre-release",
            "error",
            "misprint",
            "test card",
            "stamped",
        ]

        for priority_char in priority_order:
            for char in characteristics:
                if priority_char in char.lower():
                    return char

        return characteristics[0] if characteristics else ""

    def _normalize_set_name(self, set_name: str, unique_char: str) -> str:
        """Normalize set name and avoid duplication"""
        if not set_name:
            return ""

        # Remove redundant terms - be more aggressive about promo deduplication
        if "Promo" in unique_char:
            # Remove all variations of "Promo" from set name
            set_name = set_name.replace(" Promos", "").replace("Promos", "")
            set_name = set_name.replace(" Promo", "").replace("Promo", "")
            set_name = set_name.replace(" Promotional", "").replace("Promotional", "")

        # Common set name optimizations
        set_name = set_name.replace(" Collection", "").replace(" Series", "")

        # Clean up extra spaces
        set_name = " ".join(set_name.split())

        return set_name.strip()

    def _build_optimized_title(self, components: Dict[str, Any]) -> str:
        """Build title with intelligent character limit management"""
        MAX_LENGTH = 80

        # Essential parts that must be included
        essential = [components["game"], components["name"], components["condition"]]
        if components["language"]:
            essential.append(components["language"])

        essential_length = len(" ".join(filter(None, essential)))
        remaining_chars = MAX_LENGTH - essential_length - 2  # Buffer for spaces

        # High-value optional parts (prioritized)
        optional_parts = []

        # Add rarity (finish excluded from titles)
        if components["rarity"]:
            optional_parts.append(("rarity", components["rarity"], 3))  # High priority

        # Add unique characteristics
        if components["unique"]:
            optional_parts.append(("unique", components["unique"], 3))  # High priority

        # Add card number
        if components["number"]:
            optional_parts.append(("number", components["number"], 2))  # Medium priority

        # Add set name (most truncatable)
        if components["set"]:
            optional_parts.append(("set", components["set"], 1))  # Lower priority

        # Sort by priority (higher number = higher priority)
        optional_parts.sort(key=lambda x: x[2], reverse=True)

        # Add parts while respecting character limit
        selected_parts = []
        used_chars = 0

        for part_type, part_value, priority in optional_parts:
            part_length = len(part_value) + 1  # +1 for space

            if used_chars + part_length <= remaining_chars:
                selected_parts.append(part_value)
                used_chars += part_length
            elif part_type == "set" and priority == 1:
                # Try to truncate set name if it's the only thing left
                available_chars = remaining_chars - used_chars
                if available_chars > 8:  # Minimum useful set name length
                    truncated_set = part_value[:available_chars].strip()
                    selected_parts.append(truncated_set)
                    break

        # Build final title
        title_parts = [components["game"], components["name"]]
        title_parts.extend(selected_parts)
        title_parts.append(components["condition"])

        if components["language"]:
            title_parts.append(components["language"])

        return " ".join(filter(None, title_parts))

    def _combine_rarity_finish(self, rarity: str, finish: str) -> str:
        """Intelligently combine rarity and finish to avoid duplication"""
        if not rarity and not finish:
            return ""

        # If both contain similar terms, prefer the more specific one
        if rarity and finish:
            if "holo" in rarity.lower() and "holo" in finish.lower():
                return rarity  # Prefer "Holo Rare" over separate "Rare" + "Holo"
            return f"{rarity} {finish}"

        return rarity or finish
