"""Configuration management with environment variable support and validation"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field
from dotenv import load_dotenv

from .models import ProcessingConfig
from .utils.logger import logger


@dataclass
class Config:
    """Configuration manager with environment variable support and validation.
    
    Args:
        config_path: Path to the config.json file
        env_path: Path to the .env file (default: project_root/.env)
        
    Raises:
        ValueError: If required configuration is missing or invalid
    """
    
    config_path: str = "config.json"
    env_path: Optional[Union[str, Path]] = None
    
    def __post_init__(self):
        # Set up paths
        self.project_root = Path(__file__).parent.parent
        self._setup_environment()
        
        # Load configuration
        self.data = self._load_config()
        self.processing = self._load_processing_config()
        
        # Initialize paths
        self._setup_paths()
        
        # Validate configuration
        self._validate_config()
    
    def _setup_environment(self) -> None:
        """Load environment variables from .env file if it exists"""
        env_path = Path(self.env_path) if self.env_path else self.project_root / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.info("✅ Loaded environment variables from %s", env_path)
    
    def _setup_paths(self) -> None:
        """Initialize all file system paths"""
        # Base paths
        self.scans_folder = Path(self.data.get('scans_folder', self.project_root / 'Scans'))
        self.output_folder = Path(self.data.get('output_folder', self.project_root / 'output'))
        self.cache_folder = Path(self.data.get('cache_folder', self.output_folder / 'ultra_cache'))
        
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
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f) or {}
        except FileNotFoundError:
            logger.warning("⚠️ config.json not found at %s, using environment variables only", 
                         config_path)
            return {}
        except json.JSONDecodeError as e:
            logger.error("❌ Invalid JSON in config file: %s", e)
            return {}
    
    def _load_processing_config(self) -> ProcessingConfig:
        """Load processing configuration with environment variable fallback"""
        def get_setting(key: str, default: Any, env_key: str = None) -> Any:
            env_key = env_key or key.upper()
            return os.getenv(env_key, self.data.get('processing', {}).get(key, default))
            
        return ProcessingConfig(
            # Concurrency settings
            max_concurrent_groups=int(get_setting('max_concurrent_groups', 15)),
            max_concurrent_api_calls=int(get_setting('max_concurrent_api_calls', 25)),
            
            # Cache settings
            cache_size_gb=int(get_setting('cache_size_gb', 10)),
            cache_ttl=int(get_setting('cache_ttl', 30)),  # days
            
            # Retry settings
            retry_attempts=int(get_setting('retry_attempts', 3)),
            connection_timeout=int(get_setting('connection_timeout', 45)),
            read_timeout=int(get_setting('read_timeout', 90)),
            
            # Rate limiting (seconds between calls)
            rate_limit_ximilar=float(get_setting('rate_limit_ximilar', 0.1)),
            rate_limit_pokemon=float(get_setting('rate_limit_pokemon', 0.05)),
            rate_limit_ebay=float(get_setting('rate_limit_ebay', 0.15)),
            rate_limit_openai=float(get_setting('rate_limit_openai', 0.2)),
            rate_limit_scryfall=float(get_setting('rate_limit_scryfall', 0.1)),
            
            # Quality thresholds
            confidence_threshold_high=float(get_setting('confidence_threshold_high', 0.95)),
            confidence_threshold_medium=float(get_setting('confidence_threshold_medium', 0.85)),
            confidence_threshold_low=float(get_setting('confidence_threshold_low', 0.30)),
            
            # Pricing
            markup_percentage=float(get_setting('markup_percentage', 1.30)),
            minimum_price_floor=float(get_setting('minimum_price_floor', 1.99)),
            
            # Memory management
            max_images_in_memory=int(get_setting('max_images_in_memory', 50)),
            gc_threshold=int(get_setting('gc_threshold', 100)),
            
            # Image optimization
            auto_optimize_images=get_setting('auto_optimize_images', 'true').lower() in ('1', 'true', 'yes'),
            optimization_max_size=int(get_setting('optimization_max_size', 1600)),
            optimization_quality=int(get_setting('optimization_quality', 85)),
            optimization_format=get_setting('optimization_format', 'JPEG')
        )
    
    def _validate_config(self) -> None:
        """Validate configuration and set required attributes"""
        # Required API keys
        self.ximilar_api_key = os.getenv('XIMILAR_API_KEY') or self.data.get('ximilar_api_key')
        if not self.ximilar_api_key:
            raise ValueError("Ximilar API key is required (set XIMILAR_API_KEY in .env or config.json)")
            
        self.ximilar_endpoint = os.getenv('XIMILAR_ENDPOINT') or self.data.get('ximilar_endpoint') \
                               or 'https://api.ximilar.com/'
        
        # Optional API keys with warnings
        self.pokemon_tcg_api_key = os.getenv('POKEMON_TCG_API_KEY') or self.data.get('pokemon_tcg_api_key')
        self.openai_api_key = os.getenv('OPENAI_API_KEY') or self.data.get('openai_api_key')
        self.ebay_config = self.data.get('ebay', {})
        
        if not self.pokemon_tcg_api_key:
            logger.warning("⚠️ Pokemon TCG API key not found - some features may be limited")
        
        if not self.openai_api_key:
            logger.warning("⚠️ OpenAI API key not found - title optimization will be disabled")
    
    def get_http_session_config(self) -> Dict[str, Any]:
        """Get configuration for HTTP session"""
        return {
            'connector': {
                'limit': 200,
                'limit_per_host': 60,
                'enable_cleanup_closed': True,
                'force_close': False
            },
            'timeout': aiohttp.ClientTimeout(
                total=self.processing.connection_timeout + self.processing.read_timeout,
                connect=self.processing.connection_timeout,
                sock_read=self.processing.read_timeout
            ),
            'raise_for_status': True
        }