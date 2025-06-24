"""Simplified logging configuration"""

import logging
from typing import Optional

class TCGLogger:
    _instance: Optional['TCGLogger'] = None
    _logger: Optional[logging.Logger] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_logger()
        return cls._instance
    
    def _setup_logger(self):
        """Setup simplified logging"""
        self._logger = logging.getLogger('tcg_uploader')
        self._logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        self._logger.handlers.clear()
        
        # Console handler with simple format
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        
        # File handler
        file_handler = logging.FileHandler('tcg_uploader.log', mode='a')
        file_handler.setFormatter(logging.Formatter('%(message)s'))
        
        self._logger.addHandler(console_handler)
        self._logger.addHandler(file_handler)
    
    def info(self, message: str):
        self._logger.info(message)
    
    def error(self, message: str):
        self._logger.error(message)
    
    def warning(self, message: str):
        self._logger.warning(message)
    
    def debug(self, message: str):
        self._logger.debug(message)

# Singleton instance
logger = TCGLogger()