"""
Bulbapedia scraper for Pokemon card images (Unlimited editions)
Respectfully scrapes Bulbapedia following their guidelines
"""

import os
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import logging
from bs4 import BeautifulSoup
import json
from datetime import datetime
import hashlib

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BulbapediaScraper:
    """Scraper for Bulbapedia Pokemon card images"""
    
    def __init__(self, output_dir: str = "scraped_images", delay: float = 1.0):
        """
        Initialize the scraper
        
        Args:
            output_dir: Directory to save images
            delay: Delay between requests (respectful scraping)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Pokemon Card Database Bot - Educational Use'
        })
        
        # Cache for already downloaded images
        self.cache_file = self.output_dir / "download_cache.json"
        self.download_cache = self._load_cache()
        
    def _load_cache(self) -> Dict:
        """Load download cache"""
        if self.cache_file.exists():
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}
        
    def _save_cache(self):
        """Save download cache"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.download_cache, f, indent=2)
            
    def _get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Get a page with respectful delay"""
        try:
            time.sleep(self.delay)  # Respectful delay
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
            
    def get_base_set_unlimited_urls(self) -> Dict[str, str]:
        """Get URLs for Base Set Unlimited cards"""
        base_url = "https://bulbapedia.bulbagarden.net/wiki/Base_Set_(TCG)"
        
        logger.info("Fetching Base Set page...")
        soup = self._get_page(base_url)
        if not soup:
            return {}
            
        card_urls = {}
        
        # Find the card list table
        tables = soup.find_all('table', class_='roundy')
        
        for table in tables:
            # Look for tables with card listings
            rows = table.find_all('tr')
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    # Try to find card number and name
                    for cell in cells:
                        # Look for links to individual card pages
                        link = cell.find('a')
                        if link and '/wiki/' in link.get('href', ''):
                            href = link['href']
                            if '(Base_Set_' in href:
                                card_name = link.text.strip()
                                full_url = urljoin(base_url, href)
                                
                                # Extract card number from the row if possible
                                number_cell = cells[0].text.strip()
                                if number_cell.isdigit():
                                    card_key = f"{number_cell}_{card_name}"
                                    card_urls[card_key] = full_url
                                    
        logger.info(f"Found {len(card_urls)} Base Set card pages")
        return card_urls
        
    def _is_first_edition_image(self, img_url: str, alt_text: str = "", title_text: str = "") -> bool:
        """Check if an image is likely a 1st Edition card"""
        # Common 1st Edition indicators in filenames
        first_edition_indicators = [
            '1st', 'first', 'edition1', '1edition', '1sted', 'firsted',
            '_1_', 'ed1', 'edition_1', 'first_edition', '1st_edition'
        ]
        
        # Check URL/filename
        url_lower = img_url.lower()
        for indicator in first_edition_indicators:
            if indicator in url_lower:
                return True
                
        # Check alt and title text
        text_to_check = (alt_text + " " + title_text).lower()
        for indicator in first_edition_indicators:
            if indicator in text_to_check:
                return True
                
        # Special Bulbapedia patterns - they often use specific naming
        # For Base Set, 1st Edition images often have "Base1st" or similar
        if 'base1st' in url_lower or 'base_1st' in url_lower:
            return True
            
        # If the filename is just a number (like "2.jpg"), check surrounding context
        import re
        filename = img_url.split('/')[-1]
        if re.match(r'^\d+\.(jpg|png)$', filename):
            # Need to check other context clues
            path_parts = img_url.lower().split('/')
            for part in path_parts:
                if any(ind in part for ind in first_edition_indicators):
                    return True
                    
        return False
    
    def get_unlimited_image_from_card_page(self, card_url: str) -> Optional[str]:
        """Extract Unlimited edition image URL from a card page"""
        soup = self._get_page(card_url)
        if not soup:
            return None
            
        # Look for the card images section
        # Bulbapedia usually has a gallery or infobox with card images
        
        # First, collect all potential card images
        all_card_images = []
        
        # Strategy 1: Look in the infobox
        infobox = soup.find('table', class_='roundy')
        if infobox:
            images = infobox.find_all('img')
            for img in images:
                src = img.get('src', '')
                alt = img.get('alt', '').lower()
                title = img.get('title', '').lower()
                
                # Skip non-card images
                if any(skip in src.lower() for skip in ['symbol', 'logo', 'type', 'energy']):
                    continue
                    
                # Check if it looks like a card image
                if 'card' in src.lower() or 'base' in src.lower() or 'baseset' in src.lower():
                    all_card_images.append({
                        'src': src,
                        'alt': alt,
                        'title': title,
                        'context': 'infobox'
                    })
                    
        # Strategy 2: Look in gallery sections
        galleries = soup.find_all(['div', 'section'], class_=['gallery', 'gallerybox'])
        for gallery in galleries:
            images = gallery.find_all('img')
            for img in images:
                src = img.get('src', '')
                alt = img.get('alt', '').lower()
                title = img.get('title', '').lower()
                
                if any(skip in src.lower() for skip in ['symbol', 'logo', 'type', 'energy']):
                    continue
                    
                all_card_images.append({
                    'src': src,
                    'alt': alt,
                    'title': title,
                    'context': 'gallery'
                })
                
        # Strategy 3: All images on page
        all_images = soup.find_all('img')
        for img in all_images:
            src = img.get('src', '')
            alt = img.get('alt', '').lower()
            title = img.get('title', '').lower()
            
            # Check if it's a card image
            if any(indicator in src.lower() for indicator in ['base', 'baseset', 'card']):
                if any(skip in src.lower() for skip in ['symbol', 'logo', 'type', 'energy']):
                    continue
                    
                # Check if we already have this image
                if not any(ci['src'] == src for ci in all_card_images):
                    all_card_images.append({
                        'src': src,
                        'alt': alt,
                        'title': title,
                        'context': 'page'
                    })
                    
        # Now analyze all collected images to find the Unlimited one
        logger.info(f"Found {len(all_card_images)} potential card images")
        
        # Look for gallery sections that might contain edition comparisons
        gallery_sections = soup.find_all(['table', 'div'], class_=['wikitable', 'gallery'])
        
        # Score each image
        best_image = None
        best_score = -1
        unlimited_candidates = []
        
        for img_data in all_card_images:
            src = img_data['src']
            alt = img_data['alt']
            title = img_data['title']
            
            score = 0
            
            # Check if it's 1st Edition using our comprehensive check
            if self._is_first_edition_image(src, alt, title):
                logger.info(f"  Skipping 1st Edition image: {src[:50]}...")
                continue  # Skip this image entirely
                
            # Positive indicators for Unlimited
            if 'unlimited' in src.lower() or 'unlimited' in alt or 'unlimited' in title:
                score += 100  # Strong indicator
                unlimited_candidates.append((img_data, score))
                logger.info(f"  Found explicit Unlimited image: {src[:50]}...")
            
            # Check for shadowless (which we also don't want for standard Unlimited)
            if 'shadowless' in src or 'shadowless' in alt or 'shadowless' in title:
                score -= 50
                
            # Base Set indicators
            if 'base' in src or 'base' in alt or 'baseset' in src:
                score += 20
                
            # Look for patterns in Bulbapedia URLs
            # Often Unlimited images are named like "BaseSet2.jpg" (without 1st)
            # while 1st Edition might be "BaseSet2_1st.jpg"
            import re
            filename = src.split('/')[-1]
            
            # Check if this looks like a base set card without edition markers
            if re.match(r'^(Base|BaseSet|BS)\d+\.(jpg|png)$', filename, re.IGNORECASE):
                score += 50  # Likely Unlimited
                logger.info(f"  Found likely Unlimited pattern: {filename}")
            
            # If filename contains just the card number (like "002.jpg"), check context
            if re.match(r'^\d{1,3}\.(jpg|png)$', filename):
                # Only boost if we're sure it's not 1st Edition from context
                if img_data['context'] == 'gallery':
                    score += 20
                else:
                    score += 10
                
            # Gallery images are often the different editions
            if img_data['context'] == 'gallery':
                score += 10
                
            logger.info(f"  Image score {score}: {src[:50]}... (alt: {alt[:30]})")
            
            if score > best_score:
                best_score = score
                best_image = img_data
                
        # If we have explicit unlimited candidates, prefer those
        if unlimited_candidates:
            best_unlimited = max(unlimited_candidates, key=lambda x: x[1])
            best_image = best_unlimited[0]
            best_score = best_unlimited[1]
            
        if best_image and best_score >= 0:
            src = best_image['src']
            
            # Get full resolution URL
            if src.startswith('//'):
                src = 'https:' + src
            # Remove thumbnail parameters
            if '/thumb/' in src:
                # Extract original image URL
                parts = src.split('/thumb/')
                if len(parts) == 2:
                    original_url = parts[0] + '/' + parts[1].rsplit('/', 1)[0]
                    return original_url
            return src
            
        # Fallback: If no good image found, try looking for gallery comparisons
        logger.warning("No suitable Unlimited edition image found with normal methods")
        logger.info("Attempting fallback: Looking for edition comparison galleries...")
        
        # Look for tables or sections that compare editions
        comparison_tables = soup.find_all('table', class_='wikitable')
        for table in comparison_tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                # Look for rows that mention "Unlimited" or compare editions
                row_text = ' '.join([cell.get_text() for cell in cells]).lower()
                if 'unlimited' in row_text or ('edition' in row_text and '1st' not in row_text):
                    # Check images in this row
                    images = row.find_all('img')
                    for img in images:
                        src = img.get('src', '')
                        if src and not self._is_first_edition_image(src):
                            logger.info(f"Found potential Unlimited in comparison table: {src[:50]}...")
                            if src.startswith('//'):
                                src = 'https:' + src
                            if '/thumb/' in src:
                                parts = src.split('/thumb/')
                                if len(parts) == 2:
                                    return parts[0] + '/' + parts[1].rsplit('/', 1)[0]
                            return src
                            
        logger.error("Could not find Unlimited edition image")
        return None
        
    def download_image(self, image_url: str, save_path: Path) -> bool:
        """Download an image"""
        try:
            time.sleep(self.delay)  # Respectful delay
            response = self.session.get(image_url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Save image
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            logger.info(f"Downloaded: {save_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading {image_url}: {e}")
            return False
            
    def scrape_base_set_unlimited(self) -> Dict[str, str]:
        """Scrape all Base Set Unlimited images"""
        # Create output directory for Base Set
        base_set_dir = self.output_dir / "base_set_unlimited"
        base_set_dir.mkdir(exist_ok=True)
        
        # Get all card URLs
        card_urls = self.get_base_set_unlimited_urls()
        
        if not card_urls:
            logger.error("No card URLs found")
            return {}
            
        downloaded = {}
        
        for card_key, card_url in card_urls.items():
            # Check cache
            if card_key in self.download_cache:
                logger.info(f"Skipping {card_key} (already downloaded)")
                downloaded[card_key] = self.download_cache[card_key]
                continue
                
            logger.info(f"Processing {card_key}...")
            
            # Get image URL from card page
            image_url = self.get_unlimited_image_from_card_page(card_url)
            
            if image_url:
                # Generate filename
                card_number = card_key.split('_')[0].zfill(3)
                card_name = card_key.split('_', 1)[1].replace(' ', '_').replace('/', '_')
                filename = f"{card_number}_{card_name}_unlimited.png"
                save_path = base_set_dir / filename
                
                # Download image
                if self.download_image(image_url, save_path):
                    downloaded[card_key] = str(save_path)
                    self.download_cache[card_key] = str(save_path)
                    self._save_cache()
                    logger.info(f"Successfully downloaded {card_key}")
                else:
                    logger.error(f"Failed to download {card_key}")
            else:
                logger.warning(f"No Unlimited image found for {card_key}")
                
        logger.info(f"Download complete. Downloaded {len(downloaded)} images")
        return downloaded
        
    def scrape_specific_cards(self, card_list: List[Tuple[str, str]]) -> Dict[str, str]:
        """
        Scrape specific cards
        
        Args:
            card_list: List of tuples (card_name, bulbapedia_url)
            
        Returns:
            Dict mapping card names to downloaded file paths
        """
        downloaded = {}
        
        for card_name, card_url in card_list:
            logger.info(f"Processing {card_name}...")
            
            # Check cache
            cache_key = hashlib.md5(card_url.encode()).hexdigest()
            if cache_key in self.download_cache:
                logger.info(f"Skipping {card_name} (already downloaded)")
                downloaded[card_name] = self.download_cache[cache_key]
                continue
                
            # Get image URL
            image_url = self.get_unlimited_image_from_card_page(card_url)
            
            if image_url:
                # Generate filename
                safe_name = card_name.replace(' ', '_').replace('/', '_')
                filename = f"{safe_name}_unlimited.png"
                save_path = self.output_dir / filename
                
                # Download image
                if self.download_image(image_url, save_path):
                    downloaded[card_name] = str(save_path)
                    self.download_cache[cache_key] = str(save_path)
                    self._save_cache()
                else:
                    logger.error(f"Failed to download {card_name}")
            else:
                logger.warning(f"No Unlimited image found for {card_name}")
                
        return downloaded


if __name__ == "__main__":
    # Example usage
    scraper = BulbapediaScraper(
        output_dir="scraped_images",
        delay=2.0  # 2 second delay between requests
    )
    
    # Scrape Base Set Unlimited
    results = scraper.scrape_base_set_unlimited()
    
    print(f"\nDownloaded {len(results)} images:")
    for card, path in results.items():
        print(f"  {card}: {path}")