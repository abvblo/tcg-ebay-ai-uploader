"""Import ALL English Pokemon cards from the Pokemon TCG API"""

import asyncio
import aiohttp
from datetime import datetime
import json
import logging
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from tqdm import tqdm

from models import (
    PokemonSet, PokemonCard, Type, Subtype, CardVariation,
    init_database, get_session, DatabaseConfig
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompletePokemonImporter:
    """Import all English Pokemon cards"""
    
    def __init__(self, session: Session):
        self.session = session
        self.api_base = "https://api.pokemontcg.io/v2"
        self.headers = {}
        self.type_cache = {}
        self.subtype_cache = {}
        self.imported_cards = 0
        self.failed_cards = 0
        self.skipped_cards = 0
        
    async def import_all_english_cards(self):
        """Import all cards from English sets"""
        logger.info("Starting complete English Pokemon card import...")
        
        # Get all sets, prioritize English sets
        sets = self.session.query(PokemonSet).order_by(
            PokemonSet.release_date.desc().nullslast()
        ).all()
        
        # Count existing cards
        existing_before = self.session.query(PokemonCard).count()
        logger.info(f"Database currently has {existing_before} cards")
        
        logger.info(f"Found {len(sets)} sets to process")
        
        # Process all sets
        for set_obj in tqdm(sets, desc="Importing sets"):
            # Skip Japanese-only sets (basic filter)
            if set_obj.name and any(jp in set_obj.name.lower() for jp in ['japan', 'japanese']):
                logger.debug(f"Skipping Japanese set: {set_obj.name}")
                continue
                
            await self.import_cards_for_set(set_obj.id, set_obj.name)
            self.session.commit()  # Commit after each set
            await asyncio.sleep(0.5)  # Rate limiting
        
        # Final count
        total_cards = self.session.query(PokemonCard).count()
        
        logger.info(f"\n=== IMPORT COMPLETE ===")
        logger.info(f"Total cards in database: {total_cards}")
        logger.info(f"Cards imported in this run: {self.imported_cards}")
        logger.info(f"Cards that failed: {self.failed_cards}")
        logger.info(f"Cards skipped (already exist): {self.skipped_cards}")
        logger.info(f"Net new cards: {total_cards - existing_before}")
    
    async def import_cards_for_set(self, set_id: str, set_name: str):
        """Import all cards for a specific set"""
        async with aiohttp.ClientSession() as session:
            page = 1
            set_card_count = 0
            set_skipped = 0
            
            while True:
                # Use proper query for English cards
                url = f"{self.api_base}/cards?q=set.id:{set_id}&page={page}&pageSize=250"
                
                try:
                    async with session.get(url, headers=self.headers) as response:
                        if response.status != 200:
                            logger.error(f"API error for set {set_id}: {response.status}")
                            break
                            
                        data = await response.json()
                        
                        if not data.get('data'):
                            break
                        
                        for card_data in data['data']:
                            try:
                                # Check if card already exists
                                existing = self.session.query(PokemonCard).filter_by(
                                    api_id=card_data['id']
                                ).first()
                                
                                if existing:
                                    set_skipped += 1
                                    self.skipped_cards += 1
                                    continue
                                
                                self._import_single_card(card_data)
                                set_card_count += 1
                                self.imported_cards += 1
                                
                            except Exception as e:
                                self.failed_cards += 1
                                logger.debug(f"Failed to import card {card_data.get('id', 'unknown')}: {e}")
                        
                        if len(data['data']) < 250:
                            break
                        
                        page += 1
                        await asyncio.sleep(0.1)  # Rate limiting
                        
                except Exception as e:
                    logger.error(f"Error importing set {set_id} ({set_name}): {e}")
                    break
            
            if set_card_count > 0 or set_skipped > 0:
                logger.info(f"  {set_name}: imported {set_card_count} new cards, skipped {set_skipped} existing")
    
    def _import_single_card(self, card_data: dict):
        """Import a single card with all data"""
        # Parse HP safely
        hp = None
        if card_data.get('hp'):
            try:
                hp = int(card_data['hp'])
            except:
                pass
        
        # Create card with all available data
        card = PokemonCard(
            api_id=card_data['id'],
            name=card_data['name'],
            number=card_data['number'],
            set_id=card_data['set']['id'],
            supertype=card_data.get('supertype'),
            rarity=card_data.get('rarity'),
            hp=hp,
            artist=card_data.get('artist'),
            images=json.dumps(card_data.get('images', {})),
            evolves_from=card_data.get('evolvesFrom'),
            evolves_to=json.dumps(card_data.get('evolvesTo', [])),
            retreat_cost=json.dumps(card_data.get('retreatCost', [])),
            rules=json.dumps(card_data.get('rules', [])),
            attacks=json.dumps(card_data.get('attacks', [])),
            abilities=json.dumps(card_data.get('abilities', [])),
            weaknesses=json.dumps(card_data.get('weaknesses', [])),
            resistances=json.dumps(card_data.get('resistances', [])),
            regulation_mark=card_data.get('regulationMark'),
            tcgplayer_id=str(card_data.get('tcgplayer', {}).get('productId')) if card_data.get('tcgplayer', {}).get('productId') else None,
            cardmarket_id=str(card_data.get('cardmarket', {}).get('id')) if card_data.get('cardmarket', {}).get('id') else None
        )
        
        self.session.add(card)
        
        # Add types
        if card_data.get('types'):
            for type_name in card_data['types']:
                type_obj = self._get_or_create_type(type_name)
                if type_obj:
                    card.types.append(type_obj)
        
        # Add subtypes
        if card_data.get('subtypes'):
            for subtype_name in card_data['subtypes']:
                subtype_obj = self._get_or_create_subtype(
                    subtype_name, 
                    card_data.get('supertype', '').lower()
                )
                if subtype_obj:
                    card.subtypes.append(subtype_obj)
    
    def _get_or_create_type(self, type_name: str):
        """Get or create a type"""
        if type_name in self.type_cache:
            return self.type_cache[type_name]
        
        type_obj = self.session.query(Type).filter_by(name=type_name).first()
        if not type_obj:
            type_obj = Type(name=type_name)
            self.session.add(type_obj)
            self.session.flush()
        
        self.type_cache[type_name] = type_obj
        return type_obj
    
    def _get_or_create_subtype(self, subtype_name: str, category: str):
        """Get or create a subtype"""
        key = f"{category}:{subtype_name}"
        if key in self.subtype_cache:
            return self.subtype_cache[key]
        
        subtype_obj = self.session.query(Subtype).filter_by(
            name=subtype_name
        ).first()
        
        if not subtype_obj:
            subtype_obj = Subtype(name=subtype_name, category=category)
            self.session.add(subtype_obj)
            try:
                self.session.flush()
            except:
                self.session.rollback()
                subtype_obj = self.session.query(Subtype).filter_by(
                    name=subtype_name
                ).first()
        
        self.subtype_cache[key] = subtype_obj
        return subtype_obj


async def main():
    """Main import function"""
    # Database connection
    connection_string = DatabaseConfig.get_connection_string(
        host='localhost',
        database='pokemon_tcg',
        username='mateoallen',
        password=''
    )
    
    engine = create_engine(connection_string)
    session = get_session(engine)
    
    try:
        importer = CompletePokemonImporter(session)
        
        # Import ALL English cards
        await importer.import_all_english_cards()
        
        session.commit()
        
        # Show final statistics
        total_sets = session.query(PokemonSet).count()
        total_cards = session.query(PokemonCard).count()
        cards_with_images = session.query(PokemonCard).filter(
            PokemonCard.images.isnot(None),
            PokemonCard.images != '{}'
        ).count()
        
        logger.info(f"\n=== DATABASE STATISTICS ===")
        logger.info(f"Total sets: {total_sets}")
        logger.info(f"Total cards: {total_cards}")
        logger.info(f"Cards with images: {cards_with_images}")
        logger.info(f"Average cards per set: {total_cards / total_sets:.1f}")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    print("This will import ALL English Pokemon cards from the Pokemon TCG API.")
    print("This process may take 10-20 minutes depending on your internet connection.")
    response = input("Do you want to continue? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        asyncio.run(main())
    else:
        print("Import cancelled.")