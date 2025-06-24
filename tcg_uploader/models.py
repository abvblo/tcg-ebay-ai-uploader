"""Data models and types for TCG Uploader"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class ProcessingConfig:
    """Configuration for processing"""
    max_concurrent_groups: int = 15
    max_concurrent_api_calls: int = 25
    cache_size_gb: int = 10
    retry_attempts: int = 3
    connection_timeout: int = 45
    read_timeout: int = 90
    
    # Rate limiting (seconds between calls)
    rate_limit_ximilar: float = 0.1
    rate_limit_pokemon: float = 0.05
    rate_limit_ebay: float = 0.15
    rate_limit_openai: float = 0.2
    rate_limit_scryfall: float = 0.1
    
    # Quality thresholds
    confidence_threshold_high: float = 0.95
    confidence_threshold_medium: float = 0.85
    confidence_threshold_low: float = 0.30
    
    # Pricing
    markup_percentage: float = 1.30
    minimum_price_floor: float = 1.99
    
    # Caching
    cache_ttl: int = 30  # days
    
    # Memory management
    max_images_in_memory: int = 50
    gc_threshold: int = 100

@dataclass
class ImageGroup:
    """Represents a group of related images"""
    key: str
    paths: List[str]
    is_sequential_pair: bool = False
    front_idx: int = 0
    back_idx: int = 1

@dataclass
class CardData:
    """Complete card data"""
    # Identification
    name: str
    set_name: str
    number: str
    rarity: str
    game: str
    confidence: float
    
    # Pricing
    api_price: float = 0.0
    final_price: float = 0.0
    price_source: str = ""
    tcgplayer_link: str = ""
    
    # Additional data
    finish: str = ""
    language: str = "English"
    unique_characteristics: List[str] = field(default_factory=list)
    
    # API data
    hp: Optional[str] = None
    types: List[str] = field(default_factory=list)
    subtypes: List[str] = field(default_factory=list)
    artist: Optional[str] = None
    
    # Images
    image_urls: List[str] = field(default_factory=list)
    primary_image_url: str = ""
    
    # Processing metadata
    review_flag: str = "OK"
    processing_notes: str = ""
    processed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'set_name': self.set_name,
            'number': self.number,
            'rarity': self.rarity,
            'game': self.game,
            'confidence': self.confidence,
            'api_price': self.api_price,
            'market_price': self.final_price,
            'price_source': self.price_source,
            'tcgplayer_link': self.tcgplayer_link,
            'finish': self.finish,
            'language': self.language,
            'unique_characteristics': self.unique_characteristics,
            'hp': self.hp,
            'types': self.types,
            'subtypes': self.subtypes,
            'artist': self.artist,
            'image_urls': self.image_urls,
            'primary_image_url': self.primary_image_url,
            'review_flag': self.review_flag,
            'processing_notes': self.processing_notes,
            'processed_at': self.processed_at
        }