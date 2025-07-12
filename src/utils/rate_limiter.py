"""Advanced rate limiting with token bucket algorithm and adaptive backoff"""

import asyncio
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from ..utils.logger import logger


@dataclass
class TokenBucket:
    """Token bucket implementation for rate limiting"""

    capacity: float  # Maximum number of tokens
    refill_rate: float  # Tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self):
        self.tokens = self.capacity
        self.last_refill = time.time()

    def consume(self, tokens: float = 1.0) -> tuple[bool, float]:
        """
        Try to consume tokens from the bucket.
        Returns (success, wait_time_if_failed)
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0.0
        else:
            # Calculate wait time
            needed_tokens = tokens - self.tokens
            wait_time = needed_tokens / self.refill_rate
            return False, wait_time

    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on refill rate
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now


@dataclass
class RateLimitStats:
    """Statistics for rate limiting"""

    total_requests: int = 0
    successful_requests: int = 0
    rate_limited_requests: int = 0
    total_wait_time: float = 0.0
    last_request_time: float = field(default_factory=time.time)
    error_count: int = 0
    consecutive_errors: int = 0


class AdaptiveRateLimiter:
    """
    Advanced rate limiter with:
    - Token bucket algorithm
    - Per-endpoint rate limiting
    - Adaptive backoff based on server responses
    - Circuit breaker pattern
    """

    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {}
        self.stats: Dict[str, RateLimitStats] = defaultdict(RateLimitStats)
        self.global_bucket = TokenBucket(capacity=100, refill_rate=50)  # Global limit

        # Circuit breaker settings
        self.circuit_breaker_threshold = 5  # Consecutive errors before opening circuit
        self.circuit_breaker_reset_time = 60  # Seconds before trying again
        self.circuit_states: Dict[str, tuple[bool, float]] = {}  # (is_open, open_time)

        # Adaptive settings
        self.min_refill_rate = 0.1  # Minimum requests per second
        self.max_refill_rate = 100  # Maximum requests per second
        self.backoff_multiplier = 0.8  # Reduce rate by 20% on rate limit
        self.speedup_multiplier = 1.1  # Increase rate by 10% on success

    def configure_endpoint(
        self, endpoint: str, requests_per_second: float, burst_capacity: Optional[float] = None
    ):
        """Configure rate limiting for a specific endpoint"""
        if burst_capacity is None:
            burst_capacity = requests_per_second * 2  # Allow 2x burst by default

        self.buckets[endpoint] = TokenBucket(
            capacity=burst_capacity, refill_rate=requests_per_second
        )
        logger.info(
            f"Configured rate limit for {endpoint}: "
            f"{requests_per_second} req/s, burst: {burst_capacity}"
        )

    async def acquire(self, endpoint: str = "default", tokens: float = 1.0) -> bool:
        """
        Acquire permission to make a request.
        Returns True when ready to proceed.
        """
        # Check circuit breaker
        if self._is_circuit_open(endpoint):
            wait_time = self._get_circuit_wait_time(endpoint)
            if wait_time > 0:
                logger.warning(f"Circuit breaker open for {endpoint}, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self._reset_circuit(endpoint)

        # Get or create bucket for endpoint
        if endpoint not in self.buckets:
            self.configure_endpoint(endpoint, 10.0)  # Default 10 req/s

        bucket = self.buckets[endpoint]
        stats = self.stats[endpoint]

        # Try to consume from both endpoint and global buckets
        while True:
            # Check endpoint bucket
            endpoint_ok, endpoint_wait = bucket.consume(tokens)

            # Check global bucket
            global_ok, global_wait = self.global_bucket.consume(tokens)

            if endpoint_ok and global_ok:
                # Success
                stats.total_requests += 1
                stats.successful_requests += 1
                stats.last_request_time = time.time()

                # Adaptive speedup on success
                self._adapt_rate_on_success(endpoint)

                return True
            else:
                # Need to wait
                wait_time = max(endpoint_wait, global_wait)
                stats.total_wait_time += wait_time
                stats.rate_limited_requests += 1

                if wait_time > 0:
                    logger.debug(f"Rate limited on {endpoint}, waiting {wait_time:.3f}s")
                    await asyncio.sleep(wait_time)

                # If we had to wait for global bucket, return the token to endpoint bucket
                if not global_ok and endpoint_ok:
                    bucket.tokens += tokens

    def report_error(self, endpoint: str, is_rate_limit_error: bool = False):
        """Report an error for adaptive rate limiting"""
        stats = self.stats[endpoint]
        stats.error_count += 1
        stats.consecutive_errors += 1

        if is_rate_limit_error:
            # Server indicated rate limit - back off significantly
            self._adapt_rate_on_rate_limit(endpoint)
            logger.warning(f"Rate limit error on {endpoint}, reducing rate")

        # Check if circuit breaker should open
        if stats.consecutive_errors >= self.circuit_breaker_threshold:
            self._open_circuit(endpoint)
            logger.error(
                f"Circuit breaker opened for {endpoint} after "
                f"{stats.consecutive_errors} consecutive errors"
            )

    def report_success(self, endpoint: str):
        """Report a successful request"""
        stats = self.stats[endpoint]
        stats.consecutive_errors = 0  # Reset error counter

        # Close circuit if it was open
        if self._is_circuit_open(endpoint):
            self._reset_circuit(endpoint)
            logger.info(f"Circuit breaker closed for {endpoint}")

    def _adapt_rate_on_success(self, endpoint: str):
        """Gradually increase rate on consecutive successes"""
        stats = self.stats[endpoint]
        bucket = self.buckets[endpoint]

        # Only speed up if we haven't had errors recently
        if stats.consecutive_errors == 0 and stats.successful_requests % 100 == 0:
            new_rate = min(bucket.refill_rate * self.speedup_multiplier, self.max_refill_rate)

            if new_rate > bucket.refill_rate:
                bucket.refill_rate = new_rate
                logger.debug(f"Increased rate for {endpoint} to {new_rate:.1f} req/s")

    def _adapt_rate_on_rate_limit(self, endpoint: str):
        """Reduce rate when hitting rate limits"""
        bucket = self.buckets[endpoint]

        # Reduce rate significantly
        new_rate = max(bucket.refill_rate * self.backoff_multiplier, self.min_refill_rate)

        bucket.refill_rate = new_rate
        # Also reduce capacity to prevent bursts
        bucket.capacity = new_rate * 2
        bucket.tokens = min(bucket.tokens, bucket.capacity)

        logger.info(f"Reduced rate for {endpoint} to {new_rate:.1f} req/s")

    def _is_circuit_open(self, endpoint: str) -> bool:
        """Check if circuit breaker is open"""
        if endpoint in self.circuit_states:
            is_open, _ = self.circuit_states[endpoint]
            return is_open
        return False

    def _get_circuit_wait_time(self, endpoint: str) -> float:
        """Get remaining wait time for circuit breaker"""
        if endpoint in self.circuit_states:
            is_open, open_time = self.circuit_states[endpoint]
            if is_open:
                elapsed = time.time() - open_time
                remaining = self.circuit_breaker_reset_time - elapsed
                return max(0, remaining)
        return 0

    def _open_circuit(self, endpoint: str):
        """Open circuit breaker"""
        self.circuit_states[endpoint] = (True, time.time())

    def _reset_circuit(self, endpoint: str):
        """Reset circuit breaker"""
        if endpoint in self.circuit_states:
            del self.circuit_states[endpoint]
        self.stats[endpoint].consecutive_errors = 0

    def get_stats(self, endpoint: str) -> Dict[str, any]:
        """Get statistics for an endpoint"""
        stats = self.stats[endpoint]
        bucket = self.buckets.get(endpoint)

        return {
            "total_requests": stats.total_requests,
            "successful_requests": stats.successful_requests,
            "rate_limited_requests": stats.rate_limited_requests,
            "error_count": stats.error_count,
            "total_wait_time": stats.total_wait_time,
            "average_wait_time": stats.total_wait_time / max(1, stats.rate_limited_requests),
            "current_rate": bucket.refill_rate if bucket else 0,
            "current_capacity": bucket.capacity if bucket else 0,
            "available_tokens": bucket.tokens if bucket else 0,
            "circuit_open": self._is_circuit_open(endpoint),
            "success_rate": stats.successful_requests / max(1, stats.total_requests),
        }

    def get_all_stats(self) -> Dict[str, Dict[str, any]]:
        """Get statistics for all endpoints"""
        return {endpoint: self.get_stats(endpoint) for endpoint in self.stats.keys()}


# Global rate limiter instance
rate_limiter = AdaptiveRateLimiter()

# Configure common endpoints
rate_limiter.configure_endpoint("ximilar", 10.0, burst_capacity=20)
rate_limiter.configure_endpoint("pokemon_tcg", 20.0, burst_capacity=40)
rate_limiter.configure_endpoint("scryfall", 10.0, burst_capacity=15)
rate_limiter.configure_endpoint("ebay_eps", 6.7, burst_capacity=10)  # ~400/min
rate_limiter.configure_endpoint("openai", 5.0, burst_capacity=10)
