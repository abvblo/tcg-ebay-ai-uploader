"""
Card Recognition Module
Uses Pokémon TCG API and MTG APIs to identify cards from extracted text
"""

import requests
import re
import json
from difflib import SequenceMatcher


class CardRecognizer:
    def __init__(self, config):
        self.config = config
        self.pokemon_api_base = "https://api.pokemontcg.io/v2"
        self.scryfall_api_base = "https://api.scryfall.com"

    def identify_card(self, extracted_text, image_path):
        """Main function to identify a card from extracted text"""

        # Try Pokémon first
        pokemon_result = self.identify_pokemon_card(extracted_text)
        if pokemon_result:
            return pokemon_result

        # Try MTG if Pokémon fails
        mtg_result = self.identify_mtg_card(extracted_text)
        if mtg_result:
            return mtg_result

        return None

    def identify_pokemon_card(self, text):
        """Identify Pokémon card using Pokémon TCG API"""
        print("   🔍 Searching Pokémon database...")

        try:
            # Extract potential card name and number
            card_name = self.extract_card_name(text)
            card_number = self.extract_card_number(text)

            if not card_name:
                print("   ⚠️  No card name extracted.")
                return None

            # Build flexible query
            query_parts = [f'name:"{card_name}"']
            if card_number:
                query_parts.append(f'number:"{card_number}"')

            search_query = " ".join(query_parts)
            print(f"   🔎 Query: {search_query}")

            url = f"{self.pokemon_api_base}/cards"
            params = {"q": search_query}

            response = requests.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                if data['data']:
                    print(f"   🔎 Found {len(data['data'])} matching card(s)")
                    card = data['data'][0]  # Take first match

                    return {
                        'name': card['name'],
                        'number': card.get('number', ''),
                        'set_name': card['set']['name'],
                        'rarity': card.get('rarity', ''),
                        'finish': self.determine_finish(card),
                        'language': 'English',
                        'game': 'Pokémon',
                        'market_price': self.get_pokemon_price(card)
                    }
                else:
                    print("   ❌ No match found in Pokémon database")

            else:
                print(f"   ❌ API request failed with status code: {response.status_code}")

        except Exception as e:
            print(f"   ❌ Pokémon API error: {e}")

        return None

    def identify_mtg_card(self, text):
        """Identify MTG card using Scryfall API"""
        print("   🔍 Searching MTG database...")

        try:
            card_name = self.extract_card_name(text)
            if not card_name:
                print("   ⚠️  No card name extracted.")
                return None

            url = f"{self.scryfall_api_base}/cards/named"
            params = {"fuzzy": card_name}

            response = requests.get(url, params=params)

            if response.status_code == 200:
                card = response.json()

                print(f"   ✅ Found MTG card: {card['name']} from {card['set_name']}")

                return {
                    'name': card['name'],
                    'number': card.get('collector_number', ''),
                    'set_name': card['set_name'],
                    'rarity': card.get('rarity', ''),
                    'finish': 'Normal',
                    'language': 'English',
                    'game': 'Magic: The Gathering',
                    'market_price': self.get_mtg_price(card)
                }
            else:
                print(f"   ❌ MTG API request failed: {response.status_code}")

        except Exception as e:
            print(f"   ❌ MTG API error: {e}")

        print("   ❌ No match found in MTG database")
        return None

    def extract_card_name(self, text):
        """Extract the most likely card name from text"""
        lines = text.split('\n')
        potential_names = []

        for line in lines:
            line = line.strip()

            # Skip short or numeric-only lines
            if len(line) < 3 or line.isdigit():
                continue

            # Clean line
            clean_line = re.sub(r'[^\w\s\-\'/:]', '', line)
            words = clean_line.split()

            # Heuristic: discard lines with too many numbers
            if sum(word.isdigit() for word in words) > 1:
                continue

            potential_names.append(clean_line)

        # Return the longest line as the best guess
        if potential_names:
            best_guess = max(potential_names, key=len)
            print(f"   🧠 Extracted card name guess: {best_guess}")
            return best_guess

        return None

    def extract_card_number(self, text):
        """Extract card number (like 4/102) from text"""
        number_pattern = r'\d+\/\d+'
        matches = re.findall(number_pattern, text)

        if matches:
            print(f"   🧠 Extracted card number: {matches[0]}")
            return matches[0]

        return None

    def determine_finish(self, pokemon_card):
        """Determine if Pokémon card is Holo, Reverse Holo, etc."""
        name = pokemon_card.get('name', '').lower()
        rarity = pokemon_card.get('rarity', '').lower()

        if 'reverse' in rarity:
            return 'Reverse Holo'
        elif 'holo' in rarity:
            return 'Holo'
        else:
            return 'Normal'

    def get_pokemon_price(self, card):
        """Extract market price from Pokémon card data"""
        try:
            tcgplayer = card.get('tcgplayer', {})
            prices = tcgplayer.get('prices', {})

            for price_type in ['holofoil', 'normal', 'reverseHolofoil']:
                if price_type in prices:
                    market_price = prices[price_type].get('market')
                    if market_price:
                        return float(market_price)

            return 5.00  # Fallback price

        except:
            return 5.00

    def get_mtg_price(self, card):
        """Extract market price from MTG card data"""
        try:
            prices = card.get('prices', {})
            usd_price = prices.get('usd')

            if usd_price:
                return float(usd_price)

            return 3.00

        except:
            return 3.00