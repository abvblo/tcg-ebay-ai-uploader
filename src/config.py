"""Configuration management with environment variable support"""

import json
import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
from .models import ProcessingConfig
from .utils.logger import logger

class Config:
    def __init__(self, config_path: str = "config.json"):
        # Load environment variables
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.info("✅ Loaded environment variables from .env file")
        else:
            logger.warning("⚠️ No .env file found, using config.json only")
        
        self.config_path = Path(config_path).absolute()
        self.data = self._load_config()
        self.processing = self._load_processing_config()
        
        # Paths
        self.project_root = self.config_path.parent
        self.scans_folder = self.project_root / "Scans"
        self.output_folder = self.project_root / "output"
        self.cache_folder = self.output_folder / "ultra_cache"
        
        # Create necessary directories
        self.output_folder.mkdir(exist_ok=True)
        self.cache_folder.mkdir(exist_ok=True)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"⚠️ config.json not found at {self.config_path}, using environment variables only")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in config file: {e}")
            raise
    
    def _load_processing_config(self) -> ProcessingConfig:
        """Load processing configuration from environment or config.json"""
        return ProcessingConfig(
            max_concurrent_groups=int(os.getenv('MAX_CONCURRENT_GROUPS', 
                                              self.data.get('processing', {}).get('max_concurrent_groups', 15))),
            max_concurrent_api_calls=int(os.getenv('MAX_CONCURRENT_API_CALLS', 
                                                  self.data.get('processing', {}).get('max_concurrent_api_calls', 25))),
            cache_size_gb=int(os.getenv('CACHE_SIZE_GB', 
                                       self.data.get('processing', {}).get('cache_size_gb', 10))),
            retry_attempts=int(os.getenv('RETRY_ATTEMPTS', 
                                       self.data.get('processing', {}).get('retry_attempts', 3))),
            connection_timeout=int(os.getenv('CONNECTION_TIMEOUT', 
                                           self.data.get('processing', {}).get('connection_timeout', 45))),
            read_timeout=int(os.getenv('READ_TIMEOUT', 
                                      self.data.get('processing', {}).get('read_timeout', 90))),
            
            # Rate limiting
            rate_limit_ximilar=float(os.getenv('RATE_LIMIT_XIMILAR', 
                                              self.data.get('processing', {}).get('rate_limit_ximilar', 0.1))),
            rate_limit_pokemon=float(os.getenv('RATE_LIMIT_POKEMON', 
                                              self.data.get('processing', {}).get('rate_limit_pokemon', 0.05))),
            rate_limit_ebay=float(os.getenv('RATE_LIMIT_EBAY', 
                                           self.data.get('processing', {}).get('rate_limit_ebay', 0.15))),
            rate_limit_openai=float(os.getenv('RATE_LIMIT_OPENAI', 
                                            self.data.get('processing', {}).get('rate_limit_openai', 0.2))),
            rate_limit_scryfall=float(os.getenv('RATE_LIMIT_SCRYFALL', 
                                              self.data.get('processing', {}).get('rate_limit_scryfall', 0.1))),
            
            # Quality thresholds
            confidence_threshold_high=float(os.getenv('CONFIDENCE_THRESHOLD_HIGH', 
                                                    self.data.get('processing', {}).get('confidence_threshold_high', 0.95))),
            confidence_threshold_medium=float(os.getenv('CONFIDENCE_THRESHOLD_MEDIUM', 
                                                      self.data.get('processing', {}).get('confidence_threshold_medium', 0.85))),
            confidence_threshold_low=float(os.getenv('CONFIDENCE_THRESHOLD_LOW', 
                                                   self.data.get('processing', {}).get('confidence_threshold_low', 0.30))),
            
            # Pricing
            markup_percentage=float(os.getenv('MARKUP_PERCENTAGE', 
                                            self.data.get('processing', {}).get('markup_percentage', 1.30))),
            minimum_price_floor=float(os.getenv('MINIMUM_PRICE_FLOOR', 
                                              self.data.get('processing', {}).get('minimum_price_floor', 1.99))),
            
            # Caching
            cache_ttl=int(os.getenv('CACHE_TTL_DAYS', 
                                   self.data.get('processing', {}).get('cache_ttl', 30))),
            
            # Memory management
            max_images_in_memory=int(os.getenv('MAX_IMAGES_IN_MEMORY', 
                                              self.data.get('processing', {}).get('max_images_in_memory', 50))),
            gc_threshold=int(os.getenv('GC_THRESHOLD', 
                                      self.data.get('processing', {}).get('gc_threshold', 100))),
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.data.get(key, default)
    
    @property
    def ximilar_api_key(self) -> str:
        return os.getenv('XIMILAR_API_KEY', self.data.get('ximilar', {}).get('api_key', ''))
    
    @property
    def ximilar_endpoint(self) -> str:
        return os.getenv('XIMILAR_ENDPOINT', self.data.get('ximilar', {}).get('endpoint', ''))
    
    @property
    def pokemon_tcg_api_key(self) -> str:
        return os.getenv('POKEMON_TCG_API_KEY', self.data.get('pokemon_tcg_api_key', ''))
    
    @property
    def openai_api_key(self) -> str:
        return os.getenv('OPENAI_API_KEY', self.data.get('openai_api_key', ''))
    
    @property
    def ebay_config(self) -> Dict[str, str]:
        # Prefer environment variables over config.json
        return {
            'appid': os.getenv('EBAY_APP_ID', self.data.get('ebay_api', {}).get('appid', '')),
            'devid': os.getenv('EBAY_DEV_ID', self.data.get('ebay_api', {}).get('devid', '')),
            'certid': os.getenv('EBAY_CERT_ID', self.data.get('ebay_api', {}).get('certid', '')),
            'token': os.getenv('EBAY_USER_TOKEN', self.data.get('ebay_api', {}).get('token', '')),
        }
    
    @property
    def business_policies(self) -> Dict[str, str]:
        # Prefer environment variables over config.json
        return {
            'payment_policy_name': os.getenv('PAYMENT_POLICY_NAME', 
                                            self.data.get('business_policies', {}).get('payment_policy_name', 
                                                                                      'Immediate Payment (BIN)')),
            'shipping_policy_under_20': os.getenv('SHIPPING_POLICY_UNDER_20', 
                                                self.data.get('business_policies', {}).get('shipping_policy_under_20', 
                                                                                          'Standard Envelope 1oz (Free)')),
            'shipping_policy_over_20': os.getenv('SHIPPING_POLICY_OVER_20', 
                                               self.data.get('business_policies', {}).get('shipping_policy_over_20', 
                                                                                         'Free Shipping US GA')),
            'return_policy_name': os.getenv('RETURN_POLICY_NAME', 
                                          self.data.get('business_policies', {}).get('return_policy_name', 
                                                                                    'Returns Accepted')),
        }