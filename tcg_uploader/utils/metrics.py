"""Performance metrics tracking"""

import time
from typing import Dict, Any
from .logger import logger

class MetricsTracker:
    def __init__(self):
        self.metrics = {
            'processing_start_time': None,
            'total_cards_processed': 0,
            'successful_cards': 0,
            'failed_cards': 0,
            
            # Cache metrics
            'cache_hits': {'image': 0, 'card_data': 0, 'ebay': 0, 'title': 0},
            'cache_misses': {'image': 0, 'card_data': 0, 'ebay': 0, 'title': 0},
            
            # API calls
            'api_calls': {
                'ximilar': 0,
                'pokemon_tcg': 0,
                'scryfall': 0,
                'ebay_eps': 0,
                'openai': 0
            },
            
            # Cost tracking
            'estimated_costs': {
                'ximilar': 0.0,
                'openai': 0.0,
                'total_saved': 0.0
            },
            
            # Review flags
            'review_flags': {
                'OK': 0,
                'LOW_CONFIDENCE': 0,
                'MISSING_DATA': 0,
                'OCR_ERROR': 0
            }
        }
    
    def start_processing(self):
        """Mark start of processing"""
        self.metrics['processing_start_time'] = time.time()
    
    def record_successful_card(self):
        """Record successful card processing"""
        self.metrics['successful_cards'] += 1
        self.metrics['total_cards_processed'] += 1
    
    def record_failed_card(self):
        """Record failed card processing"""
        self.metrics['failed_cards'] += 1
        self.metrics['total_cards_processed'] += 1
    
    def record_cache_hit(self, cache_type: str):
        """Record cache hit"""
        if cache_type in self.metrics['cache_hits']:
            self.metrics['cache_hits'][cache_type] += 1
    
    def record_cache_miss(self, cache_type: str):
        """Record cache miss"""
        if cache_type in self.metrics['cache_misses']:
            self.metrics['cache_misses'][cache_type] += 1
    
    def record_api_call(self, api_name: str):
        """Record API call"""
        if api_name in self.metrics['api_calls']:
            self.metrics['api_calls'][api_name] += 1
            
            # Update costs
            if api_name == 'ximilar':
                self.metrics['estimated_costs']['ximilar'] += 0.01
            elif api_name == 'openai':
                self.metrics['estimated_costs']['openai'] += 0.06
    
    def record_review_flag(self, flag: str):
        """Record review flag"""
        if flag in self.metrics['review_flags']:
            self.metrics['review_flags'][flag] += 1
    
    def calculate_savings(self):
        """Calculate cost savings from caching"""
        # Ximilar savings
        ximilar_saved = self.metrics['cache_hits']['image'] * 0.01
        
        # Other savings
        ebay_saved = self.metrics['cache_hits']['ebay'] * 0.005
        
        self.metrics['estimated_costs']['total_saved'] = ximilar_saved + ebay_saved
    
    def print_summary(self, successful_cards: int):
        """Print processing summary"""
        if not self.metrics['processing_start_time']:
            return
        
        processing_time = time.time() - self.metrics['processing_start_time']
        self.calculate_savings()
        
        logger.info("\n" + "=" * 50)
        logger.info(f"✅ Processed {successful_cards} cards in {processing_time:.1f} seconds")
        logger.info(f"💰 API costs saved: ${self.metrics['estimated_costs']['total_saved']:.2f}")
        
        # Review items
        review_count = sum(
            count for flag, count in self.metrics['review_flags'].items() 
            if flag != 'OK'
        )
        logger.info(f"📊 Items needing review: {review_count}")
        
        logger.info("=" * 50)