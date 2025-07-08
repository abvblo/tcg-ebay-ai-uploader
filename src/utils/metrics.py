"""
Metrics collection and reporting for the TCG eBay Batch Uploader.

This module provides a MetricsTracker class for collecting, aggregating, and reporting
performance metrics and operational statistics.
"""

import time
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging

logger = logging.getLogger(__name__)

@dataclass
class ProcessingMetrics:
    """Metrics for card processing operations"""
    total_cards: int = 0
    cards_processed: int = 0
    cards_failed: int = 0
    avg_processing_time: float = 0.0
    total_processing_time: float = 0.0
    api_calls: int = 0
    api_errors: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ExcelGenerationMetrics:
    """Metrics for Excel file generation"""
    num_listings: int = 0
    num_rows: int = 0
    duration_seconds: float = 0.0
    file_size_mb: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class APIMetrics:
    """Metrics for API usage"""
    total_calls: int = 0
    failed_calls: int = 0
    total_time: float = 0.0
    avg_response_time: float = 0.0
    endpoint_metrics: Dict[str, Dict[str, Union[int, float]]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class MetricsTracker:
    """
    Tracks and reports metrics for the TCG eBay Batch Uploader.
    
    This class provides methods to record various metrics during application
    execution and generate reports.
    """
    
    def __init__(self, output_dir: Optional[Union[str, Path]] = None):
        """
        Initialize the metrics tracker.
        
        Args:
            output_dir: Directory to save metrics reports. If None, reports won't be saved to disk.
        """
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        
        # Initialize metrics
        self.processing = ProcessingMetrics()
        self.excel_generation = ExcelGenerationMetrics()
        self.api = APIMetrics()
        
        # Set up output directory
        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir and not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Track individual operations
        self.operation_times: Dict[str, List[float]] = {}
        self.error_log: List[Dict[str, Any]] = []
        self.warning_log: List[Dict[str, Any]] = []
    
    def start_timer(self, operation_name: str) -> None:
        """Start timing an operation"""
        self.operation_times[operation_name] = [time.time()]
    
    def end_timer(self, operation_name: str) -> float:
        """
        End timing an operation and return the duration.
        
        Args:
            operation_name: Name of the operation to end timing for.
            
        Returns:
            float: Duration of the operation in seconds.
            
        Raises:
            KeyError: If the operation was not started.
        """
        if operation_name not in self.operation_times or not self.operation_times[operation_name]:
            raise KeyError(f"Operation '{operation_name}' was not started or already ended")
            
        end_time = time.time()
        start_time = self.operation_times[operation_name][0]
        duration = end_time - start_time
        
        # Store the end time and duration
        if len(self.operation_times[operation_name]) == 1:
            self.operation_times[operation_name].extend([end_time, duration])
        else:
            self.operation_times[operation_name][1] = end_time
            self.operation_times[operation_name][2] = duration
        
        return duration
    
    def record_operation(self, operation_name: str, duration: float) -> None:
        """
        Record a completed operation with its duration.
        
        Args:
            operation_name: Name of the operation.
            duration: Duration in seconds.
        """
        if operation_name not in self.operation_times:
            self.operation_times[operation_name] = []
        self.operation_times[operation_name].extend([time.time() - duration, time.time(), duration])
    
    def record_error(self, error_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Record an error that occurred during processing.
        
        Args:
            error_type: Type/category of the error.
            message: Error message.
            details: Additional error details as a dictionary.
        """
        error = {
            'timestamp': datetime.utcnow().isoformat(),
            'type': error_type,
            'message': message,
            'details': details or {}
        }
        self.error_log.append(error)
        logger.error(f"{error_type}: {message}", extra={'details': details})
    
    def record_warning(self, warning_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a warning that occurred during processing.
        
        Args:
            warning_type: Type/category of the warning.
            message: Warning message.
            details: Additional warning details as a dictionary.
        """
        warning = {
            'timestamp': datetime.utcnow().isoformat(),
            'type': warning_type,
            'message': message,
            'details': details or {}
        }
        self.warning_log.append(warning)
        logger.warning(f"{warning_type}: {message}", extra={'details': details})
    
    def record_api_call(self, endpoint: str, duration: float, success: bool = True) -> None:
        """
        Record an API call with its duration and success status.
        
        Args:
            endpoint: The API endpoint that was called.
            duration: Duration of the API call in seconds.
            success: Whether the API call was successful.
        """
        self.api.total_calls += 1
        self.api.total_time += duration
        self.api.avg_response_time = (
            (self.api.avg_response_time * (self.api.total_calls - 1) + duration) / 
            self.api.total_calls
        )
        
        if not success:
            self.api.failed_calls += 1
        
        # Track metrics per endpoint
        if endpoint not in self.api.endpoint_metrics:
            self.api.endpoint_metrics[endpoint] = {
                'calls': 0,
                'errors': 0,
                'total_time': 0.0,
                'avg_time': 0.0
            }
        
        endpoint_metrics = self.api.endpoint_metrics[endpoint]
        endpoint_metrics['calls'] += 1
        endpoint_metrics['total_time'] += duration
        endpoint_metrics['avg_time'] = endpoint_metrics['total_time'] / endpoint_metrics['calls']
        
        if not success:
            endpoint_metrics['errors'] += 1
    
    def record_processing_metrics(
        self, 
        cards_processed: int = 0, 
        cards_failed: int = 0, 
        processing_time: float = 0.0,
        cache_hits: int = 0,
        cache_misses: int = 0
    ) -> None:
        """
        Record card processing metrics.
        
        Args:
            cards_processed: Number of cards successfully processed.
            cards_failed: Number of cards that failed processing.
            processing_time: Time taken to process the cards in seconds.
            cache_hits: Number of cache hits during processing.
            cache_misses: Number of cache misses during processing.
        """
        self.processing.cards_processed += cards_processed
        self.processing.cards_failed += cards_failed
        self.processing.total_processing_time += processing_time
        self.processing.cache_hits += cache_hits
        self.processing.cache_misses += cache_misses
        
        total_processed = self.processing.cards_processed + self.processing.cards_failed
        if total_processed > 0:
            self.processing.avg_processing_time = self.processing.total_processing_time / total_processed
    
    def record_excel_generation(
        self,
        num_listings: int,
        num_rows: int,
        duration_seconds: float
    ) -> None:
        """
        Record metrics for Excel file generation.
        
        Args:
            num_listings: Number of listings in the Excel file.
            num_rows: Total number of rows in the Excel file.
            duration_seconds: Time taken to generate the Excel file in seconds.
        """
        self.excel_generation.num_listings = num_listings
        self.excel_generation.num_rows = num_rows
        self.excel_generation.duration_seconds = duration_seconds
    
    def finalize(self) -> Dict[str, Any]:
        """
        Finalize metrics collection and return a summary.
        
        Returns:
            Dict containing all collected metrics.
        """
        self.end_time = time.time()
        
        # Calculate total runtime
        total_runtime = self.end_time - self.start_time
        
        # Prepare the metrics summary
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'runtime_seconds': total_runtime,
            'processing': self.processing.to_dict(),
            'excel_generation': self.excel_generation.to_dict(),
            'api': self.api.to_dict(),
            'operation_times': {
                op: {
                    'start_time': times[0],
                    'end_time': times[1],
                    'duration_seconds': times[2]
                } for op, times in self.operation_times.items()
            },
            'errors': self.error_log,
            'warnings': self.warning_log,
            'error_count': len(self.error_log),
            'warning_count': len(self.warning_log),
            'success_rate': (
                (self.processing.cards_processed / 
                 (self.processing.cards_processed + self.processing.cards_failed)) * 100
                if (self.processing.cards_processed + self.processing.cards_failed) > 0 else 100.0
            )
        }
        
        # Save to file if output directory is configured
        if self.output_dir:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            metrics_file = self.output_dir / f'metrics_{timestamp}.json'
            
            try:
                with open(metrics_file, 'w') as f:
                    json.dump(summary, f, indent=2)
                logger.info(f"Metrics saved to {metrics_file}")
            except Exception as e:
                logger.error(f"Failed to save metrics to file: {e}")
        
        return summary
    
    def get_summary(self) -> str:
        """
        Get a human-readable summary of the metrics.
        
        Returns:
            str: Formatted summary string.
        """
        summary = self.finalize()
        
        # Format the summary
        lines = [
            "=" * 80,
            "TCG EBAY BATCH UPLOADER - METRICS SUMMARY",
            "=" * 80,
            f"Timestamp: {summary['timestamp']}",
            f"Total Runtime: {summary['runtime_seconds']:.2f} seconds",
            "",
            "PROCESSING METRICS:",
            f"  • Cards Processed: {self.processing.cards_processed}",
            f"  • Cards Failed: {self.processing.cards_failed}",
            f"  • Success Rate: {summary['success_rate']:.1f}%",
            f"  • Avg Processing Time: {self.processing.avg_processing_time:.3f} seconds/card",
            f"  • Cache Hit Rate: {self.processing.cache_hits / (self.processing.cache_hits + self.processing.cache_misses) * 100:.1f}%"
            if (self.processing.cache_hits + self.processing.cache_misses) > 0 else "  • No cache data",
            "",
            "EXCEL GENERATION:",
            f"  • Listings: {self.excel_generation.num_listings}",
            f"  • Total Rows: {self.excel_generation.num_rows}",
            f"  • Generation Time: {self.excel_generation.duration_seconds:.2f} seconds",
            "",
            "API USAGE:",
            f"  • Total API Calls: {self.api.total_calls}",
            f"  • Failed API Calls: {self.api.failed_calls}",
            f"  • Avg Response Time: {self.api.avg_response_time * 1000:.1f} ms",
            "",
            "OPERATION TIMES:"
        ]
        
        # Add operation times
        for op, times in self.operation_times.items():
            if len(times) >= 3:  # Ensure we have start, end, and duration
                lines.append(f"  • {op}: {times[2]:.3f} seconds")
        
        # Add error/warning counts
        lines.extend([
            "",
            "ERRORS AND WARNINGS:",
            f"  • Errors: {summary['error_count']}",
            f"  • Warnings: {summary['warning_count']}"
        ])
        
        # Add endpoint metrics
        if self.api.endpoint_metrics:
            lines.extend(["", "ENDPOINT METRICS:"])
            for endpoint, metrics in self.api.endpoint_metrics.items():
                lines.extend([
                    f"  • {endpoint}:",
                    f"    - Calls: {metrics['calls']}",
                    f"    - Errors: {metrics['errors']}",
                    f"    - Avg Time: {metrics['avg_time'] * 1000:.1f} ms"
                ])
        
        lines.append("=" * 80)
        return "\n".join(lines)