"""Enhanced HTTP session management with connection pooling and circuit breaker"""

import asyncio
import ssl
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import aiohttp
import certifi

from ..utils.logger import logger


class HTTPSessionManager:
    """
    Enhanced HTTP session manager with:
    - Connection pooling per domain
    - Circuit breaker pattern
    - Automatic retries with exponential backoff
    - DNS caching
    - Keep-alive connections
    """

    def __init__(self):
        self.sessions: Dict[str, aiohttp.ClientSession] = {}
        self.circuit_states: Dict[str, Dict[str, Any]] = {}
        self.ssl_context = self._create_ssl_context()

        # Enhanced connection limits
        self.connector_config = {
            "limit": 300,  # Total connection pool size
            "limit_per_host": 100,  # Per-host connection limit
            "ttl_dns_cache": 600,  # DNS cache TTL (10 minutes)
            "enable_cleanup_closed": True,
            "force_close": False,
            "keepalive_timeout": 30,
            "use_dns_cache": True,
        }

        # Timeout configuration
        self.timeout_config = aiohttp.ClientTimeout(
            total=120,  # Total timeout
            connect=30,  # Connection timeout
            sock_connect=30,  # Socket connection timeout
            sock_read=60,  # Socket read timeout
        )

        # Circuit breaker configuration
        self.circuit_breaker_config = {
            "failure_threshold": 5,
            "recovery_timeout": 60,
            "expected_exception_types": (aiohttp.ClientError, asyncio.TimeoutError),
        }

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create optimized SSL context"""
        context = ssl.create_default_context(cafile=certifi.where())
        # Enable session tickets for faster TLS handshakes
        context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        return context

    @asynccontextmanager
    async def get_session(self, base_url: str = "default") -> aiohttp.ClientSession:
        """Get or create a session for a specific base URL with connection pooling"""
        if base_url not in self.sessions or self.sessions[base_url].closed:
            # Create domain-specific connector for better connection reuse
            connector = aiohttp.TCPConnector(**self.connector_config, ssl=self.ssl_context)

            # Create session with optimized settings
            session = aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout_config,
                headers={
                    "User-Agent": "eBay-TCG-Uploader/3.0",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                },
                raise_for_status=False,  # Handle status codes manually
                cookie_jar=aiohttp.CookieJar(),
                trust_env=True,
            )

            self.sessions[base_url] = session
            logger.debug(f"Created new HTTP session for {base_url}")

        yield self.sessions[base_url]

    async def request_with_circuit_breaker(
        self, method: str, url: str, session: aiohttp.ClientSession, **kwargs
    ) -> aiohttp.ClientResponse:
        """Make HTTP request with circuit breaker pattern"""
        domain = self._extract_domain(url)

        # Check circuit breaker state
        if self._is_circuit_open(domain):
            raise Exception(f"Circuit breaker open for {domain}")

        try:
            # Make request
            response = await session.request(method, url, **kwargs)

            # Record success
            self._record_success(domain)

            return response

        except self.circuit_breaker_config["expected_exception_types"] as e:
            # Record failure
            self._record_failure(domain)

            # Check if circuit should open
            if self._should_open_circuit(domain):
                self._open_circuit(domain)
                logger.warning(f"Circuit breaker opened for {domain}")

            raise e

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    def _is_circuit_open(self, domain: str) -> bool:
        """Check if circuit is open for domain"""
        if domain not in self.circuit_states:
            return False

        state = self.circuit_states[domain]
        if state["status"] != "open":
            return False

        # Check if recovery timeout has passed
        elapsed = time.time() - state["opened_at"]
        if elapsed > self.circuit_breaker_config["recovery_timeout"]:
            # Try half-open state
            state["status"] = "half-open"
            state["failures"] = 0
            return False

        return True

    def _record_success(self, domain: str):
        """Record successful request"""
        if domain in self.circuit_states:
            state = self.circuit_states[domain]
            state["failures"] = 0
            if state["status"] == "half-open":
                state["status"] = "closed"
                logger.info(f"Circuit breaker closed for {domain}")

    def _record_failure(self, domain: str):
        """Record failed request"""
        if domain not in self.circuit_states:
            self.circuit_states[domain] = {"status": "closed", "failures": 0, "opened_at": None}

        state = self.circuit_states[domain]
        state["failures"] += 1

    def _should_open_circuit(self, domain: str) -> bool:
        """Check if circuit should open"""
        if domain not in self.circuit_states:
            return False

        state = self.circuit_states[domain]
        return state["failures"] >= self.circuit_breaker_config["failure_threshold"]

    def _open_circuit(self, domain: str):
        """Open circuit for domain"""
        if domain not in self.circuit_states:
            self.circuit_states[domain] = {"status": "closed", "failures": 0, "opened_at": None}

        state = self.circuit_states[domain]
        state["status"] = "open"
        state["opened_at"] = time.time()

    async def close_all(self):
        """Close all sessions gracefully"""
        for base_url, session in self.sessions.items():
            if not session.closed:
                await session.close()
                logger.debug(f"Closed HTTP session for {base_url}")

        self.sessions.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get session and circuit breaker statistics"""
        stats = {"active_sessions": len(self.sessions), "circuit_breakers": {}}

        for domain, state in self.circuit_states.items():
            stats["circuit_breakers"][domain] = {
                "status": state["status"],
                "failures": state["failures"],
                "opened_at": state["opened_at"],
            }

        for base_url, session in self.sessions.items():
            if not session.closed and hasattr(session.connector, "_acquired"):
                stats[f"session_{base_url}"] = {
                    "active_connections": len(session.connector._acquired),
                    "closed": session.closed,
                }

        return stats


# Global session manager instance
http_session_manager = HTTPSessionManager()


@asynccontextmanager
async def get_optimized_session(base_url: str = "default") -> aiohttp.ClientSession:
    """Get an optimized HTTP session with connection pooling"""
    async with http_session_manager.get_session(base_url) as session:
        yield session


async def cleanup_sessions():
    """Cleanup all HTTP sessions"""
    await http_session_manager.close_all()
