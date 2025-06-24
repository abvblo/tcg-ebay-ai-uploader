"""Configuration management"""

import json
from pathlib import Path
from typing import Dict, Any
from .models import ProcessingConfig
from .utils.logger import logger

class Config:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path).absolute()
        self.data = self._load_config()
        self.processing = ProcessingConfig()
        
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
            logger.error(f"❌ config.json not found at {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in config file: {e}")
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.data.get(key, default)
    
    @property
    def ximilar_api_key(self) -> str:
        return self.data.get('ximilar', {}).get('api_key', '')
    
    @property
    def ximilar_endpoint(self) -> str:
        return self.data.get('ximilar', {}).get('endpoint', '')
    
    @property
    def pokemon_tcg_api_key(self) -> str:
        return self.data.get('pokemon_tcg_api_key', '')
    
    @property
    def openai_api_key(self) -> str:
        return self.data.get('openai_api_key', '')
    
    @property
    def ebay_config(self) -> Dict[str, str]:
        return self.data.get('ebay_api', {})
    
    @property
    def business_policies(self) -> Dict[str, str]:
        return self.data.get('business_policies', {})