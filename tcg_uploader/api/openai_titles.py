"""OpenAI Title Optimizer"""

from openai import AsyncOpenAI
import asyncio
from typing import List, Dict, Any
import re
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
            batch = cards[i:i + self.batch_size]
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
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # Parse response
            titles_text = response.choices[0].message.content.strip()
            titles = [title.strip() for title in titles_text.split('\n') if title.strip()]
            
            # Remove numbering
            titles = [re.sub(r'^\d+\.\s*', '', title) for title in titles]
            
            # Ensure we have enough titles
            while len(titles) < len(batch):
                titles.append(self._generate_fallback_title(batch[len(titles)]))
            
            return titles[:len(batch)]
            
        except Exception as e:
            logger.error(f"❌ OpenAI API error: {e}")
            return [self._generate_fallback_title(card) for card in batch]
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for OpenAI"""
        return """You are a TCG market eBay listing expert with deep knowledge of Pokemon, Magic: The Gathering, Yu-Gi-Oh, and other trading card games. You understand what buyers search for and what sells.

    MANDATORY TEMPLATE: [Game] {Card Name} {Card Number}/{Total Cards} {Set Name} {Rarity} {Finish} {Unique Characteristic} {Condition}

    CRITICAL RULES:
    1. ALWAYS start with the game name: "Pokémon" for Pokemon cards, "MTG" for Magic cards
    2. Card numbers: use "25/102" format when both number and total are available
    3. NEVER include boring/default terms that don't add value:
       - Skip: Normal, Regular, Standard, Basic (as finish)
       - Skip: Common (unless it's the actual rarity)
       - Skip: Non-Holo, Non-Foil
       - Skip: English (NEVER include - English is assumed)
    4. ALWAYS include meaningful terms:
       - Rarities: Rare, Uncommon, Common, Secret Rare, Ultra Rare, etc.
       - Finishes: Holo, Reverse Holo, Foil, Rainbow, Gold, Full Art, Alt Art
       - Unique Characteristics: 1st Edition, Shadowless, Unlimited, Stamped, Promo, Staff, Error, Misprint, Pre-release
    5. Condition is ALWAYS "NM/LP" (Near Mint/Lightly Played)
    6. ONLY add "JP" at the end for Japanese cards - NEVER mention English
    7. eBay character limit: 80 characters max
    8. Use spaces between elements, no pipe separators

    LANGUAGE RULES:
    - English cards: NEVER mention language
    - Japanese cards: Add "JP" at the end ONLY
    - No other language indicators needed

    UNIQUE CHARACTERISTICS (only include if present):
    - Edition markers: 1st Edition, Shadowless, Unlimited
    - Print runs: Alpha, Beta, Revised, 4th Edition
    - Promotional: Promo, Staff, Championship, Tournament, Pre-release
    - Errors/Variants: Error, Misprint, Test Card, Square Cut
    - Special stamps: Stamped, League, Convention stamps

    EXAMPLES:
    ✓ Pokémon Charizard 4/102 Base Set Holo Rare NM/LP
    ✓ Pokémon Charizard 4/102 Base Set Holo Rare 1st Edition NM/LP
    ✓ Pokémon Pikachu 58/102 Base Set NM/LP
    ✓ Pokémon Mewtwo 10/102 Base Set Holo Shadowless NM/LP
    ✓ MTG Black Lotus Alpha Rare NM/LP
    ✓ Pokémon Ancient Mew Promo Holo NM/LP
    ✓ Pokémon Dark Charizard 4/82 Team Rocket Holo Rare NM/LP JP
    ✓ MTG Lightning Bolt Beta NM/LP
    ✓ Pokémon Tropical Mega Battle No. 2 Trainer Promo NM/LP
    ✓ Pokémon Bulbasaur 44/102 Base Set Shadowless NM/LP

    Remember: You're a market expert. Only include terms that matter to buyers and affect value."""
    
    def _build_user_prompt(self, batch: List[Dict[str, Any]]) -> str:
        """Build user prompt for batch"""
        prompt = "Optimize these TCG card titles for eBay:\n\n"
        
        for idx, card in enumerate(batch):
            unique_chars = ', '.join(card.get('unique_characteristics', [])) or 'None'
            prompt += (f"{idx + 1}. Game: {card.get('game', '')}, "
                      f"Name: {card.get('name', '')}, "
                      f"Number: {card.get('number', '')}, "
                      f"Set: {card.get('set_name', '')}, "
                      f"Rarity: {card.get('rarity', '')}, "
                      f"Finish: {card.get('finish', '')}, "
                      f"Unique Characteristics: {unique_chars}, "
                      f"Language: {card.get('language', 'English')}\n")
        
        return prompt
    
    def _generate_fallback_title(self, card_data: Dict[str, Any]) -> str:
        """Generate fallback title when OpenAI is unavailable"""
        # Get game prefix
        game = card_data.get('game', 'Pokémon')
        if game.lower() in ['pokémon', 'pokemon']:
            game_prefix = 'Pokémon'
        elif game.lower() in ['magic: the gathering', 'mtg']:
            game_prefix = 'MTG'
        else:
            game_prefix = game
        
        # Build title parts
        parts = [game_prefix]
        
        if card_data.get('name'):
            parts.append(card_data['name'])
        
        if card_data.get('number'):
            parts.append(card_data['number'])
        
        if card_data.get('set_name'):
            parts.append(card_data['set_name'])
        
        # Add rarity if meaningful
        rarity = card_data.get('rarity', '').strip()
        if rarity and rarity.lower() not in ['common', 'normal', 'regular']:
            parts.append(rarity)
        
        # Add finish if meaningful
        finish = card_data.get('finish', '').strip()
        if finish and finish.lower() not in ['normal', 'regular', 'standard']:
            parts.append(finish)
        
        # Add unique characteristics
        for char in card_data.get('unique_characteristics', [])[:1]:
            parts.append(char)
            break
        
        # Always add condition
        parts.append('NM/LP')
        
        # Add language if not English
        if card_data.get('language', 'English').lower() in ['japanese', 'jp']:
            parts.append('JP')
        
        # Join and truncate if needed
        title = ' '.join(parts)
        if len(title) > 80:
            title = title[:77] + "..."
        
        return title