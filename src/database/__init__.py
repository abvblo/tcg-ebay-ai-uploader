"""Database module for Pokemon card reference and price tracking"""

from .crud import (
    CardCRUD,
    CardSearchFilters,
    PriceCRUD,
    SetCRUD,
    ValidationCRUD,
    get_or_create_card,
    get_or_create_set,
    persist_api_card_data,
)
from .models import (
    Base,
    CardVariation,
    PokemonCard,
    PokemonSet,
    PriceSnapshot,
    Subtype,
    Type,
    ValidationRule,
    XimilarCorrection,
    get_session,
    init_database,
)

# Backward compatibility alias
Card = PokemonCard
from .service import DatabaseService, get_db_service

__all__ = [
    # Models
    "PokemonCard",
    "Card",  # Backward compatibility alias
    "PokemonSet",
    "Type",
    "Subtype",
    "CardVariation",
    "PriceSnapshot",
    "ValidationRule",
    "XimilarCorrection",
    "Base",
    "init_database",
    "get_session",
    # Service
    "DatabaseService",
    "get_db_service",
    # CRUD
    "CardCRUD",
    "SetCRUD",
    "PriceCRUD",
    "ValidationCRUD",
    "CardSearchFilters",
    "get_or_create_card",
    "get_or_create_set",
    "persist_api_card_data",
]
