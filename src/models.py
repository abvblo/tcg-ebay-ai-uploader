"""Data models for TCG eBay uploader"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProcessingConfig:
    """Processing configuration with defaults"""

    # Concurrency settings
    max_concurrent_groups: int = 15
    max_concurrent_api_calls: int = 25

    # Cache settings
    cache_size_gb: int = 10
    cache_ttl: int = 30  # days

    # Retry settings
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

    # Memory management
    max_images_in_memory: int = 50
    gc_threshold: int = 100

    # Image optimization settings
    auto_optimize_images: bool = True
    optimization_max_size: int = 1600  # pixels on longest side
    optimization_quality: int = 85  # JPEG quality 1-100
    optimization_format: str = "JPEG"  # 'JPEG' or 'PNG'


@dataclass
class ImageGroup:
    """Group of related images (front/back of same card)"""

    key: str
    paths: List[str]
    is_sequential_pair: bool = False
    front_idx: int = 0
    back_idx: int = 1


@dataclass
class CardData:
    """Processed card data ready for eBay listing"""

    # Core identification
    name: str
    set_name: str
    number: str
    rarity: str
    game: str
    confidence: float

    def __post_init__(self):
        """Validate card data after initialization"""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
        if self.final_price < 0:
            raise ValueError(f"Final price must be non-negative, got {self.final_price}")
        if self.api_price < 0:
            raise ValueError(f"API price must be non-negative, got {self.api_price}")

    # Card details
    finish: str = ""
    unique_characteristics: List[str] = field(default_factory=list)
    language: str = "English"

    # Pricing
    api_price: float = 5.00
    final_price: float = 5.00
    price_source: str = "Default"
    tcgplayer_link: str = ""

    # Processing metadata
    review_flag: str = "OK"
    processing_notes: str = ""

    # Images
    image_urls: List[str] = field(default_factory=list)
    primary_image_url: str = ""

    # Additional API data
    hp: Optional[str] = None
    types: List[str] = field(default_factory=list)
    subtypes: List[str] = field(default_factory=list)
    artist: Optional[str] = None
    release_date: Optional[str] = None

    # MTG specific
    power: Optional[str] = None
    toughness: Optional[str] = None

    # Card size (for oversized cards)
    card_size: str = "Standard"

    # Variation-specific fields
    is_variation_parent: bool = False
    variation_count: int = 1
    variations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        data = {
            "name": self.name,
            "set_name": self.set_name,
            "number": self.number,
            "rarity": self.rarity,
            "game": self.game,
            "confidence": self.confidence,
            "finish": self.finish,
            "unique_characteristics": self.unique_characteristics,
            "language": self.language,
            "api_price": self.api_price,
            "final_price": self.final_price,
            "price_source": self.price_source,
            "tcgplayer_link": self.tcgplayer_link,
            "review_flag": self.review_flag,
            "processing_notes": self.processing_notes,
            "image_urls": self.image_urls,
            "primary_image_url": self.primary_image_url,
            # Add variation fields
            "is_variation_parent": self.is_variation_parent,
            "variation_count": self.variation_count,
            "variations": self.variations,
        }

        # Include optional fields if present
        if self.hp:
            data["hp"] = self.hp
        if self.types:
            data["types"] = self.types
        if self.subtypes:
            data["subtypes"] = self.subtypes
        if self.artist:
            data["artist"] = self.artist
        if self.release_date:
            data["release_date"] = self.release_date
        if self.power:
            data["power"] = self.power
        if self.toughness:
            data["toughness"] = self.toughness
        if self.card_size != "Standard":
            data["card_size"] = self.card_size

        return data
