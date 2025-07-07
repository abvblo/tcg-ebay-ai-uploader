"""
Script to update the database with Unlimited edition images from Bulbapedia
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.scrapers.bulbapedia_scraper import BulbapediaScraper
from src.database.models import db, Card, CardVariation
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
from PIL import Image
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UnlimitedImageUpdater:
    """Updates database with Unlimited edition images"""
    
    def __init__(self, db_url: str = None):
        """Initialize the updater"""
        if not db_url:
            # Get from environment
            from dotenv import load_dotenv
            load_dotenv()
            db_url = os.getenv('DATABASE_URL', 'postgresql://mateo:pokemon@localhost:5432/pokemon_cards')
            
        self.engine = create_engine(db_url)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Image directory for web app
        self.web_image_dir = Path(__file__).parent.parent / "web/static/images/pokemon/base1"
        self.web_image_dir.mkdir(parents=True, exist_ok=True)
        
    def get_base_set_cards(self):
        """Get all Base Set cards from database"""
        return self.session.query(Card).filter(
            Card.set_id == 'base1'  # Base Set ID
        ).all()
        
    def update_card_with_unlimited_image(self, card: Card, image_path: str) -> bool:
        """Update a card with Unlimited edition image"""
        try:
            # Copy image to web directory
            source_path = Path(image_path)
            if not source_path.exists():
                logger.error(f"Image not found: {image_path}")
                return False
                
            # Generate web-friendly filename
            dest_filename = f"{card.number}_unlimited.png"
            dest_path = self.web_image_dir / dest_filename
            
            # Copy and optimize image
            with Image.open(source_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                    
                # Save optimized image
                img.save(dest_path, 'PNG', optimize=True)
                
            logger.info(f"Copied image for {card.name} #{card.number}")
            
            # Update card image path for Unlimited variation
            unlimited_variation = self.session.query(CardVariation).filter(
                CardVariation.card_id == card.id,
                CardVariation.edition == 'unlimited'
            ).first()
            
            if unlimited_variation:
                unlimited_variation.image_url = f"/static/images/pokemon/base1/{dest_filename}"
                self.session.commit()
                logger.info(f"Updated Unlimited variation for {card.name}")
            else:
                # Create Unlimited variation if it doesn't exist
                new_variation = CardVariation(
                    card_id=card.id,
                    edition='unlimited',
                    foil_type='normal',
                    image_url=f"/static/images/pokemon/base1/{dest_filename}"
                )
                self.session.add(new_variation)
                self.session.commit()
                logger.info(f"Created Unlimited variation for {card.name}")
                
            return True
            
        except Exception as e:
            logger.error(f"Error updating card {card.name}: {e}")
            self.session.rollback()
            return False
            
    def update_base_set_unlimited(self):
        """Update all Base Set cards with Unlimited images"""
        # First, scrape the images
        logger.info("Starting Bulbapedia scrape for Base Set Unlimited...")
        scraper = BulbapediaScraper(
            output_dir="scraped_images/base_set",
            delay=2.0  # Respectful delay
        )
        
        # Get specific card URLs for Base Set
        base_set_urls = [
            ("Alakazam", "https://bulbapedia.bulbagarden.net/wiki/Alakazam_(Base_Set_1)"),
            ("Blastoise", "https://bulbapedia.bulbagarden.net/wiki/Blastoise_(Base_Set_2)"),
            ("Chansey", "https://bulbapedia.bulbagarden.net/wiki/Chansey_(Base_Set_3)"),
            ("Charizard", "https://bulbapedia.bulbagarden.net/wiki/Charizard_(Base_Set_4)"),
            ("Clefairy", "https://bulbapedia.bulbagarden.net/wiki/Clefairy_(Base_Set_5)"),
            ("Gyarados", "https://bulbapedia.bulbagarden.net/wiki/Gyarados_(Base_Set_6)"),
            ("Hitmonchan", "https://bulbapedia.bulbagarden.net/wiki/Hitmonchan_(Base_Set_7)"),
            ("Machamp", "https://bulbapedia.bulbagarden.net/wiki/Machamp_(Base_Set_8)"),
            ("Magneton", "https://bulbapedia.bulbagarden.net/wiki/Magneton_(Base_Set_9)"),
            ("Mewtwo", "https://bulbapedia.bulbagarden.net/wiki/Mewtwo_(Base_Set_10)"),
            ("Nidoking", "https://bulbapedia.bulbagarden.net/wiki/Nidoking_(Base_Set_11)"),
            ("Ninetales", "https://bulbapedia.bulbagarden.net/wiki/Ninetales_(Base_Set_12)"),
            ("Poliwrath", "https://bulbapedia.bulbagarden.net/wiki/Poliwrath_(Base_Set_13)"),
            ("Raichu", "https://bulbapedia.bulbagarden.net/wiki/Raichu_(Base_Set_14)"),
            ("Venusaur", "https://bulbapedia.bulbagarden.net/wiki/Venusaur_(Base_Set_15)"),
            ("Zapdos", "https://bulbapedia.bulbagarden.net/wiki/Zapdos_(Base_Set_16)"),
            # Add more as needed...
        ]
        
        # Scrape images
        downloaded = scraper.scrape_specific_cards(base_set_urls)
        
        if not downloaded:
            logger.error("No images were downloaded")
            return
            
        # Update database
        logger.info("Updating database with Unlimited images...")
        cards = self.get_base_set_cards()
        
        updated = 0
        for card in cards:
            # Try to match downloaded image
            for card_name, image_path in downloaded.items():
                if card.name.lower() == card_name.lower():
                    if self.update_card_with_unlimited_image(card, image_path):
                        updated += 1
                    break
                    
        logger.info(f"Updated {updated} cards with Unlimited images")
        
    def run_full_update(self):
        """Run full update process"""
        try:
            logger.info("Starting full Unlimited image update...")
            self.update_base_set_unlimited()
            logger.info("Update complete!")
        except Exception as e:
            logger.error(f"Error during update: {e}")
            self.session.rollback()
        finally:
            self.session.close()


if __name__ == "__main__":
    updater = UnlimitedImageUpdater()
    updater.run_full_update()