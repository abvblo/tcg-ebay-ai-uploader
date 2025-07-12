"""Performance monitoring and reporting utilities"""

import asyncio
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils.http_session import http_session_manager
from ..utils.logger import logger
from ..utils.rate_limiter import rate_limiter


@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""

    name: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    operations: int = 0
    errors: int = 0
    bytes_processed: int = 0

    @property
    def duration(self) -> float:
        """Get duration in seconds"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @property
    def operations_per_second(self) -> float:
        """Calculate operations per second"""
        duration = self.duration
        return self.operations / duration if duration > 0 else 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        total = self.operations + self.errors
        return (self.operations / total * 100) if total > 0 else 100


class PerformanceMonitor:
    """Monitor and report on application performance"""

    def __init__(self):
        self.metrics: Dict[str, PerformanceMetrics] = {}
        self.operation_times: Dict[str, List[float]] = defaultdict(list)
        self.baseline_metrics: Optional[Dict[str, Any]] = None

    def start_operation(self, name: str) -> PerformanceMetrics:
        """Start tracking a performance metric"""
        metric = PerformanceMetrics(name=name)
        self.metrics[name] = metric
        return metric

    def end_operation(
        self, name: str, operations: int = 1, bytes_processed: int = 0, errors: int = 0
    ):
        """End tracking a performance metric"""
        if name in self.metrics:
            metric = self.metrics[name]
            metric.end_time = time.time()
            metric.operations += operations
            metric.bytes_processed += bytes_processed
            metric.errors += errors

            # Track operation time
            self.operation_times[name].append(metric.duration)

    def record_operation_time(self, name: str, duration: float):
        """Record a single operation time"""
        self.operation_times[name].append(duration)

    def get_statistics(self, name: str) -> Dict[str, float]:
        """Get statistical analysis for an operation"""
        times = self.operation_times.get(name, [])

        if not times:
            return {}

        return {
            "count": len(times),
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "stdev": statistics.stdev(times) if len(times) > 1 else 0,
            "percentile_95": sorted(times)[int(len(times) * 0.95)] if times else 0,
        }

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        report = {
            "metrics": {},
            "statistics": {},
            "rate_limiting": rate_limiter.get_all_stats(),
            "http_sessions": http_session_manager.get_stats(),
            "improvements": {},
        }

        # Add metrics
        for name, metric in self.metrics.items():
            report["metrics"][name] = {
                "duration": metric.duration,
                "operations": metric.operations,
                "operations_per_second": metric.operations_per_second,
                "success_rate": metric.success_rate,
                "bytes_processed": metric.bytes_processed,
                "mb_per_second": (
                    (metric.bytes_processed / 1024 / 1024) / metric.duration
                    if metric.duration > 0
                    else 0
                ),
            }

        # Add statistics
        for name in self.operation_times:
            report["statistics"][name] = self.get_statistics(name)

        # Calculate improvements if baseline exists
        if self.baseline_metrics:
            report["improvements"] = self._calculate_improvements()

        return report

    def _calculate_improvements(self) -> Dict[str, Any]:
        """Calculate performance improvements from baseline"""
        improvements = {}

        if not self.baseline_metrics:
            return improvements

        # Compare current metrics with baseline
        for name, metric in self.metrics.items():
            if name in self.baseline_metrics:
                baseline = self.baseline_metrics[name]

                # Calculate improvement percentages
                duration_improvement = (
                    (baseline["duration"] - metric.duration) / baseline["duration"] * 100
                    if baseline["duration"] > 0
                    else 0
                )

                ops_improvement = (
                    (metric.operations_per_second - baseline["operations_per_second"])
                    / baseline["operations_per_second"]
                    * 100
                    if baseline["operations_per_second"] > 0
                    else 0
                )

                improvements[name] = {
                    "duration_improvement": f"{duration_improvement:.1f}%",
                    "throughput_improvement": f"{ops_improvement:.1f}%",
                    "baseline_duration": baseline["duration"],
                    "current_duration": metric.duration,
                    "baseline_ops_per_sec": baseline["operations_per_second"],
                    "current_ops_per_sec": metric.operations_per_second,
                }

        return improvements

    def set_baseline(self):
        """Set current metrics as baseline for comparison"""
        self.baseline_metrics = {}

        for name, metric in self.metrics.items():
            self.baseline_metrics[name] = {
                "duration": metric.duration,
                "operations": metric.operations,
                "operations_per_second": metric.operations_per_second,
                "bytes_processed": metric.bytes_processed,
            }

    def print_report(self):
        """Print formatted performance report"""
        report = self.get_performance_report()

        logger.info("\n" + "=" * 60)
        logger.info("PERFORMANCE REPORT")
        logger.info("=" * 60)

        # Print metrics
        logger.info("\n📊 Operation Metrics:")
        for name, data in report["metrics"].items():
            logger.info(f"\n  {name}:")
            logger.info(f"    Duration: {data['duration']:.2f}s")
            logger.info(f"    Operations: {data['operations']}")
            logger.info(f"    Throughput: {data['operations_per_second']:.2f} ops/s")
            logger.info(f"    Success Rate: {data['success_rate']:.1f}%")
            if data["bytes_processed"] > 0:
                logger.info(f"    Data Rate: {data['mb_per_second']:.2f} MB/s")

        # Print statistics
        logger.info("\n📈 Operation Statistics:")
        for name, stats in report["statistics"].items():
            if stats:
                logger.info(f"\n  {name}:")
                logger.info(f"    Mean: {stats['mean']:.3f}s")
                logger.info(f"    Median: {stats['median']:.3f}s")
                logger.info(f"    95th Percentile: {stats['percentile_95']:.3f}s")
                logger.info(f"    Min/Max: {stats['min']:.3f}s / {stats['max']:.3f}s")

        # Print improvements
        if report["improvements"]:
            logger.info("\n🚀 Performance Improvements:")
            for name, improvement in report["improvements"].items():
                logger.info(f"\n  {name}:")
                logger.info(f"    Duration: {improvement['duration_improvement']} faster")
                logger.info(f"    Throughput: {improvement['throughput_improvement']} increase")
                logger.info(f"    Before: {improvement['baseline_ops_per_sec']:.2f} ops/s")
                logger.info(f"    After: {improvement['current_ops_per_sec']:.2f} ops/s")

        # Print rate limiting stats
        logger.info("\n🔄 Rate Limiting Statistics:")
        for endpoint, stats in report["rate_limiting"].items():
            if stats["total_requests"] > 0:
                logger.info(f"\n  {endpoint}:")
                logger.info(f"    Total Requests: {stats['total_requests']}")
                logger.info(f"    Success Rate: {stats['success_rate']:.1%}")
                logger.info(f"    Rate Limited: {stats['rate_limited_requests']}")
                logger.info(f"    Current Rate: {stats['current_rate']:.1f} req/s")
                logger.info(f"    Circuit Open: {stats['circuit_open']}")

        logger.info("\n" + "=" * 60)


# Global performance monitor instance
performance_monitor = PerformanceMonitor()
