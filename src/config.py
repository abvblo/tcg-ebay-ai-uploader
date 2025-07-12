"""Configuration management with environment variable support and validation"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import aiohttp
from dotenv import load_dotenv

# Flexible imports that work both as package and direct execution
try:
    from .models import ProcessingConfig
    from .utils.logger import logger
except ImportError:
    # Direct execution fallback
    import sys
    from pathlib import Path

    # Add src directory to path for direct execution
    src_dir = Path(__file__).parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from models import ProcessingConfig
    from utils.logger import logger


@dataclass
class SecurityConfig:
    """Security configuration for web application"""

    # Environment settings
    flask_env: str = "development"
    flask_debug: bool = True
    flask_host: str = "127.0.0.1"
    flask_port: int = 5001

    # Security settings
    secret_key: Optional[str] = None
    session_cookie_secure: bool = False
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = "Lax"

    # HTTPS settings
    force_https: bool = False
    hsts_max_age: int = 31536000  # 1 year

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_storage: str = "memory://"
    default_rate_limit: List[str] = field(
        default_factory=lambda: ["1000 per hour", "100 per minute"]
    )

    # CORS settings
    cors_origins: List[str] = field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5001"]
    )

    # CSP settings
    csp_enabled: bool = True
    csp_report_only: bool = False

    # Logging
    security_logging: bool = True
    log_requests: bool = False

    @classmethod
    def from_env(cls) -> "SecurityConfig":
        """Create security config from environment variables"""
        flask_env = os.getenv("FLASK_ENV", "development")
        is_production = flask_env == "production"

        return cls(
            flask_env=flask_env,
            flask_debug=not is_production,
            flask_host=os.getenv("FLASK_HOST", "127.0.0.1"),
            flask_port=int(os.getenv("FLASK_PORT", "5001")),
            secret_key=os.getenv("FLASK_SECRET_KEY"),
            session_cookie_secure=is_production,
            session_cookie_httponly=True,
            session_cookie_samesite="Strict" if is_production else "Lax",
            force_https=is_production,
            hsts_max_age=31536000 if is_production else 0,
            rate_limit_enabled=True,
            rate_limit_storage=os.getenv("REDIS_URL", "memory://"),
            cors_origins=[
                origin.strip()
                for origin in os.getenv(
                    "CORS_ORIGINS", "http://localhost:3000,http://localhost:5001"
                ).split(",")
            ],
            csp_enabled=True,
            csp_report_only=not is_production,
            security_logging=True,
            log_requests=is_production,
        )


@dataclass
class Config:
    """Configuration manager with environment variable support and validation.

    Args:
        config_path: Path to the config.json file
        env_path: Path to the .env file (default: project_root/.env)

    Raises:
        ValueError: If required configuration is missing or invalid
    """

    config_path: str = "config/config.json"
    env_path: Optional[Union[str, Path]] = None

    def __post_init__(self):
        # Set up paths
        self.project_root = Path(__file__).parent.parent
        self._setup_environment()

        # Load configuration
        self.data = self._load_config()
        self.processing = self._load_processing_config()
        self.security = SecurityConfig.from_env()

        # Initialize paths
        self._setup_paths()

        # Validate configuration
        self._validate_config()

        # Set up business policies
        self._setup_business_policies()

    def _setup_environment(self) -> None:
        """Load environment variables from .env file if it exists"""
        env_path = Path(self.env_path) if self.env_path else self.project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"✅ Loaded environment variables from {env_path}")

    def _setup_paths(self) -> None:
        """Initialize all file system paths"""
        # Base paths
        self.scans_folder = Path(self.data.get("scans_folder", self.project_root / "input"))
        self.output_folder = Path(self.data.get("output_folder", self.project_root / "output"))
        self.cache_folder = Path(self.data.get("cache_folder", self.output_folder / "ultra_cache"))

        # Create necessary directories
        self.scans_folder.mkdir(exist_ok=True, parents=True)
        self.output_folder.mkdir(exist_ok=True, parents=True)
        self.cache_folder.mkdir(exist_ok=True, parents=True)

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        config_path = Path(self.config_path)
        if not config_path.is_absolute():
            config_path = self.project_root / config_path

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except FileNotFoundError:
            logger.warning(
                f"⚠️ config.json not found at {config_path}, using environment variables only"
            )
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in config file: {e}")
            return {}

    def _load_processing_config(self) -> ProcessingConfig:
        """Load processing configuration with environment variable fallback"""

        def get_setting(key: str, default: Any, env_key: str = None) -> Any:
            env_key = env_key or key.upper()
            return os.getenv(env_key, self.data.get("processing", {}).get(key, default))

        return ProcessingConfig(
            # Concurrency settings
            max_concurrent_groups=int(get_setting("max_concurrent_groups", 15)),
            max_concurrent_api_calls=int(get_setting("max_concurrent_api_calls", 25)),
            # Cache settings
            cache_size_gb=int(get_setting("cache_size_gb", 10)),
            cache_ttl=int(get_setting("cache_ttl", 30)),  # days
            # Retry settings
            retry_attempts=int(get_setting("retry_attempts", 3)),
            connection_timeout=int(get_setting("connection_timeout", 45)),
            read_timeout=int(get_setting("read_timeout", 90)),
            # Rate limiting (seconds between calls)
            rate_limit_ximilar=float(get_setting("rate_limit_ximilar", 0.1)),
            rate_limit_pokemon=float(get_setting("rate_limit_pokemon", 0.05)),
            rate_limit_ebay=float(get_setting("rate_limit_ebay", 0.15)),
            rate_limit_openai=float(get_setting("rate_limit_openai", 0.2)),
            rate_limit_scryfall=float(get_setting("rate_limit_scryfall", 0.1)),
            # Quality thresholds
            confidence_threshold_high=float(get_setting("confidence_threshold_high", 0.95)),
            confidence_threshold_medium=float(get_setting("confidence_threshold_medium", 0.85)),
            confidence_threshold_low=float(get_setting("confidence_threshold_low", 0.30)),
            # Pricing
            markup_percentage=float(get_setting("markup_percentage", 1.30)),
            minimum_price_floor=float(get_setting("minimum_price_floor", 1.99)),
            # Memory management
            max_images_in_memory=int(get_setting("max_images_in_memory", 50)),
            gc_threshold=int(get_setting("gc_threshold", 100)),
            # Image optimization
            auto_optimize_images=get_setting("auto_optimize_images", "true").lower()
            in ("1", "true", "yes"),
            optimization_max_size=int(get_setting("optimization_max_size", 1600)),
            optimization_quality=int(get_setting("optimization_quality", 85)),
            optimization_format=get_setting("optimization_format", "JPEG"),
        )

    def _validate_config(self) -> None:
        """Validate configuration and set required attributes"""
        # Required API keys
        self.ximilar_api_key = os.getenv("XIMILAR_API_KEY") or self.data.get("ximilar", {}).get(
            "api_key"
        )
        if not self.ximilar_api_key or self.ximilar_api_key == "your_ximilar_api_key_here":
            logger.warning("⚠️ WARNING: Ximilar API key not found. Some features may be limited.")

        self.ximilar_endpoint = (
            os.getenv("XIMILAR_ENDPOINT")
            or self.data.get("ximilar", {}).get("endpoint")
            or "https://api.ximilar.com/collectibles/v2/tcg_id"
        )

        # Authentication configuration
        self.auth_enabled = os.getenv("AUTH_ENABLED", "true").lower() in ("1", "true", "yes")
        self.secret_key = (
            os.getenv("SECRET_KEY")
            or self.data.get("secret_key")
            or "dev-secret-key-change-in-production"
        )
        self.api_key = os.getenv("API_KEY") or self.data.get("api_key") or "tcg-uploader-api-key"
        self.admin_username = (
            os.getenv("ADMIN_USERNAME") or self.data.get("admin_username") or "admin"
        )
        self.admin_password = (
            os.getenv("ADMIN_PASSWORD") or self.data.get("admin_password") or "admin123"
        )

        # Database configuration
        self.database_url = (
            os.getenv("DATABASE_URL")
            or self.data.get("database_url")
            or "postgresql://mateo:pokemon@localhost:5432/pokemon_cards"
        )
        self.database_pool_size = int(os.getenv("DATABASE_POOL_SIZE", "20"))
        self.database_max_overflow = int(os.getenv("DATABASE_MAX_OVERFLOW", "40"))

        # Optional API keys with warnings
        self.pokemon_tcg_api_key = os.getenv("POKEMON_TCG_API_KEY") or self.data.get(
            "pokemon_tcg_api_key"
        )
        self.openai_api_key = os.getenv("OPENAI_API_KEY") or self.data.get("openai_api_key")

        # Store original values for security validation before potentially nullifying them
        original_pokemon_key = self.pokemon_tcg_api_key
        original_openai_key = self.openai_api_key

        # eBay configuration - try both ebay_api and ebay keys, also check environment variables
        self.ebay_config = self.data.get("ebay_api", self.data.get("ebay", {}))

        # Override with environment variables if available
        if os.getenv("EBAY_APP_ID"):
            self.ebay_config["appid"] = os.getenv("EBAY_APP_ID")
        if os.getenv("EBAY_DEV_ID"):
            self.ebay_config["devid"] = os.getenv("EBAY_DEV_ID")
        if os.getenv("EBAY_CERT_ID"):
            self.ebay_config["certid"] = os.getenv("EBAY_CERT_ID")
        if os.getenv("EBAY_USER_TOKEN"):
            self.ebay_config["token"] = os.getenv("EBAY_USER_TOKEN")
        
        # SECURITY: Check for placeholder values and raise error if found
        placeholder_found = False
        placeholder_keys = []
        
        # Check API keys for placeholder values
        if self.ximilar_api_key == "your_ximilar_api_key_here":
            placeholder_found = True
            placeholder_keys.append("XIMILAR_API_KEY")
            
        if original_pokemon_key == "your_pokemon_tcg_api_key_here":
            placeholder_found = True
            placeholder_keys.append("POKEMON_TCG_API_KEY")
            
        if original_openai_key == "your_openai_api_key_here":
            placeholder_found = True
            placeholder_keys.append("OPENAI_API_KEY")
        
        # Check database credentials for placeholder values
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST")
        db_name = os.getenv("DB_NAME")
        
        if db_user == "your_db_user_here":
            placeholder_found = True
            placeholder_keys.append("DB_USER")
        if db_password == "your_db_password_here":
            placeholder_found = True
            placeholder_keys.append("DB_PASSWORD")
        if db_host == "your_db_host_here":
            placeholder_found = True
            placeholder_keys.append("DB_HOST")
        if db_name == "your_db_name_here":
            placeholder_found = True
            placeholder_keys.append("DB_NAME")
        
        # Check eBay configuration for placeholder values
        ebay_placeholder_found = False
        ebay_placeholder_keys = []
        if self.ebay_config:  # Check if ebay_config is not empty
            for key, value in self.ebay_config.items():
                if isinstance(value, str) and value.startswith("your_ebay_"):
                    ebay_placeholder_found = True
                    ebay_placeholder_keys.append(f"EBAY_{key.upper()}")
        
        # Add eBay placeholder keys if any were found
        if ebay_placeholder_found:
            placeholder_found = True
            placeholder_keys.extend(ebay_placeholder_keys)
        
        # Raise security error if any placeholder values were detected
        if placeholder_found:
            raise ValueError(
                f"SECURITY: Application cannot start with placeholder credential values. "
                f"Please update the following keys in your .env file: {', '.join(placeholder_keys)}. "
                f"Copy .env.template to .env and replace placeholder values with your actual credentials."
            )

        # Now apply the modifications after security check
        # Validate placeholder values for Pokemon TCG API key
        if self.pokemon_tcg_api_key == "your_pokemon_tcg_api_key_here":
            self.pokemon_tcg_api_key = None
            logger.warning("⚠️ Pokemon TCG API key is placeholder - some features may be limited")
        elif not self.pokemon_tcg_api_key:
            logger.warning("⚠️ Pokemon TCG API key not found - some features may be limited")

        # Validate placeholder values for OpenAI API key
        if self.openai_api_key == "your_openai_api_key_here":
            self.openai_api_key = None
            logger.warning("⚠️ OpenAI API key is placeholder - title optimization will be disabled")
        elif not self.openai_api_key:
            logger.warning("⚠️ OpenAI API key not found - title optimization will be disabled")
        
        # Validate eBay placeholder values and nullify them
        if self.ebay_config:  # Check if ebay_config is not empty
            for key, value in list(self.ebay_config.items()):  # Use list() to avoid runtime modification issues
                if isinstance(value, str) and value.startswith("your_ebay_"):
                    self.ebay_config[key] = None
                    logger.warning(f"⚠️ eBay {key} is placeholder - eBay features will be limited")

    def _setup_business_policies(self) -> None:
        """Set up eBay business policies with defaults"""
        # Get business policies from config or use defaults
        business_policies_config = self.data.get("business_policies", {})

        # Default eBay business policies
        default_policies = {
            "payment_policy_id": business_policies_config.get(
                "payment_policy_id", "DEFAULT_PAYMENT"
            ),
            "return_policy_id": business_policies_config.get("return_policy_id", "DEFAULT_RETURN"),
            "shipping_policy_id": business_policies_config.get(
                "shipping_policy_id", "DEFAULT_SHIPPING"
            ),
            "fulfillment_policy_id": business_policies_config.get(
                "fulfillment_policy_id", "DEFAULT_FULFILLMENT"
            ),
        }

        # Set business policies attribute
        self.business_policies = default_policies

        # Also set individual policy attributes for backward compatibility
        self.payment_policy_id = default_policies["payment_policy_id"]
        self.return_policy_id = default_policies["return_policy_id"]
        self.shipping_policy_id = default_policies["shipping_policy_id"]
        self.fulfillment_policy_id = default_policies["fulfillment_policy_id"]

        logger.info("✅ Business policies configured")

    def get_http_session_config(self) -> Dict[str, Any]:
        """Get configuration for HTTP session"""
        return {
            "connector": {
                "limit": 200,
                "limit_per_host": 60,
                "enable_cleanup_closed": True,
                "force_close": False,
            },
            "timeout": aiohttp.ClientTimeout(
                total=self.processing.connection_timeout + self.processing.read_timeout,
                connect=self.processing.connection_timeout,
                sock_read=self.processing.read_timeout,
            ),
            "raise_for_status": True,
        }

    @property
    def ebay_app_id(self) -> Optional[str]:
        """Get the eBay application ID from config"""
        return self.ebay_config.get("appid")

    def get_database_url(self) -> str:
        """Get the database URL"""
        return self.database_url
