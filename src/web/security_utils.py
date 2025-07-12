"""Security utilities for SQL injection prevention and input validation"""

import logging
import re
from functools import wraps
from typing import Any, Dict, List, Optional, Union

from flask import jsonify, request
from sqlalchemy import bindparam, text
from sqlalchemy.sql.sqltypes import Integer, String

logger = logging.getLogger(__name__)

# Security constants
MAX_QUERY_LENGTH = 100
MAX_FILTER_LENGTH = 50
MAX_SORT_LENGTH = 20
MAX_PER_PAGE = 100
MIN_AUTOCOMPLETE_LENGTH = 2

# SQL injection patterns to detect
SQL_INJECTION_PATTERNS = [
    r"union\s+select",
    r"drop\s+table",
    r"delete\s+from",
    r"update\s+.*\s+set",
    r"insert\s+into",
    r"create\s+table",
    r"alter\s+table",
    r"exec\s*\(",
    r"sp_\w+",
    r"xp_\w+",
    r"--",
    r"/\*.*\*/",
    r";\s*shutdown",
    r";\s*drop",
    r";\s*delete",
    r";\s*update",
    r";\s*insert",
    r"char\s*\(",
    r"ascii\s*\(",
    r"substring\s*\(",
    r"waitfor\s+delay",
    r"benchmark\s*\(",
    r"sleep\s*\(",
    r"pg_sleep\s*\(",
    r"extractvalue\s*\(",
    r"updatexml\s*\(",
    r"load_file\s*\(",
    r"into\s+outfile",
    r"into\s+dumpfile",
    r"'\s*or\s*'",
    r"'\s*or\s*\d+\s*=\s*\d+",
    r"'\s*and\s*'",
    r"'\s*and\s*\d+\s*=\s*\d+",
    r"'\s*/\*",
    r"\*/\s*'",
    r"0x[0-9a-fA-F]+",
    r"concat\s*\(",
    r"group_concat\s*\(",
    r"having\s+\d+\s*=\s*\d+",
    r"order\s+by\s+\d+",
    r"information_schema",
    r"sys\.",
    r"mysql\.",
    r"pg_",
    r"version\s*\(",
    r"database\s*\(",
    r"user\s*\(",
    r"@@",
    r"null\s*,\s*null",
    r"true\s*,\s*false",
    r"false\s*,\s*true",
]

# Whitelist for sort parameters
ALLOWED_SORT_FIELDS = {
    "name",
    "name_desc",
    "number",
    "number_desc",
    "hp",
    "hp_desc",
    "set",
    "set_old",
}

# Whitelist for filter parameters
ALLOWED_FILTER_FIELDS = {"set", "type", "rarity", "edition", "characteristics"}

# Whitelist for characteristics
ALLOWED_CHARACTERISTICS = {
    "holo",
    "reverse",
    "full-art",
    "secret",
    "rainbow",
    "gold",
    "shining",
    "stamped",
    "prerelease",
    "staff",
}


def escape_sql_like(value: str) -> str:
    """
    Escape special characters in SQL LIKE patterns

    Args:
        value: Input string to escape

    Returns:
        Escaped string safe for SQL LIKE operations
    """
    if not isinstance(value, str):
        return str(value)

    # Escape SQL LIKE wildcards and special characters
    escaped = value.replace("\\", "\\\\")  # Escape backslashes first
    escaped = escaped.replace("%", "\\%")  # Escape percent signs
    escaped = escaped.replace("_", "\\_")  # Escape underscores
    escaped = escaped.replace("'", "''")  # Escape single quotes

    return escaped


def validate_search_query(query: str) -> str:
    """
    Validate and sanitize search query input

    Args:
        query: Raw search query from user

    Returns:
        Sanitized query string

    Raises:
        ValueError: If query contains suspicious patterns
    """
    if not query:
        return ""

    # Length check
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"Query too long (max {MAX_QUERY_LENGTH} characters)")

    # Check for SQL injection patterns
    query_lower = query.lower()
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            logger.warning(f"Potential SQL injection attempt detected: {query}")
            raise ValueError("Invalid characters in search query")

    # Remove dangerous characters
    # Allow: letters, numbers, spaces, hyphens, apostrophes, periods
    sanitized = re.sub(r"[^a-zA-Z0-9\s\-\'.&]", "", query)

    # Remove extra whitespace
    sanitized = " ".join(sanitized.split())

    return sanitized[:MAX_QUERY_LENGTH]


def validate_filter_value(value: str, field_name: str) -> str:
    """
    Validate filter parameter values

    Args:
        value: Filter value from user
        field_name: Name of the filter field

    Returns:
        Sanitized filter value

    Raises:
        ValueError: If value is invalid
    """
    if not value:
        return ""

    # Check field name is allowed
    if field_name not in ALLOWED_FILTER_FIELDS:
        raise ValueError(f"Invalid filter field: {field_name}")

    # Length check
    if len(value) > MAX_FILTER_LENGTH:
        raise ValueError(f"Filter value too long (max {MAX_FILTER_LENGTH} characters)")

    # Special validation for characteristics
    if field_name == "characteristics" and value not in ALLOWED_CHARACTERISTICS:
        raise ValueError(f"Invalid characteristic value: {value}")

    # Check for SQL injection patterns
    value_lower = value.lower()
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, value_lower, re.IGNORECASE):
            logger.warning(f"Potential SQL injection in filter {field_name}: {value}")
            raise ValueError("Invalid characters in filter value")

    # Sanitize the value
    sanitized = re.sub(r"[^a-zA-Z0-9\s\-\'.&]", "", value)
    sanitized = " ".join(sanitized.split())

    return sanitized[:MAX_FILTER_LENGTH]


def validate_sort_parameter(sort_value: str) -> str:
    """
    Validate sort parameter

    Args:
        sort_value: Sort parameter from user

    Returns:
        Validated sort value

    Raises:
        ValueError: If sort value is invalid
    """
    if not sort_value:
        return "name"  # Default sort

    if len(sort_value) > MAX_SORT_LENGTH:
        raise ValueError(f"Sort parameter too long (max {MAX_SORT_LENGTH} characters)")

    if sort_value not in ALLOWED_SORT_FIELDS:
        raise ValueError(f"Invalid sort field: {sort_value}")

    return sort_value


def validate_pagination_params(page: Any, per_page: Any) -> tuple[int, int]:
    """
    Validate pagination parameters

    Args:
        page: Page number from user
        per_page: Items per page from user

    Returns:
        Tuple of (validated_page, validated_per_page)

    Raises:
        ValueError: If parameters are invalid
    """
    try:
        page_int = int(page) if page else 1
        per_page_int = int(per_page) if per_page else 20
    except (ValueError, TypeError):
        raise ValueError("Invalid pagination parameters")

    if page_int < 1:
        page_int = 1

    if per_page_int < 1:
        per_page_int = 20
    elif per_page_int > MAX_PER_PAGE:
        per_page_int = MAX_PER_PAGE

    return page_int, per_page_int


def validate_autocomplete_query(query: str) -> str:
    """
    Validate autocomplete query

    Args:
        query: Autocomplete query from user

    Returns:
        Sanitized query string

    Raises:
        ValueError: If query is invalid
    """
    if not query:
        return ""

    # Length checks
    if len(query) < MIN_AUTOCOMPLETE_LENGTH:
        raise ValueError(f"Query too short (min {MIN_AUTOCOMPLETE_LENGTH} characters)")

    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"Query too long (max {MAX_QUERY_LENGTH} characters)")

    # Check for SQL injection patterns
    query_lower = query.lower()
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            logger.warning(f"Potential SQL injection in autocomplete: {query}")
            raise ValueError("Invalid characters in query")

    # Sanitize - be more restrictive for autocomplete
    sanitized = re.sub(r"[^a-zA-Z0-9\s\-\']", "", query)
    sanitized = " ".join(sanitized.split())

    return sanitized[:MAX_QUERY_LENGTH]


def secure_like_query(field, value: str, prefix_only: bool = False) -> Any:
    """
    Create a secure LIKE query using parameterized queries

    Args:
        field: SQLAlchemy field to query
        value: Value to search for
        prefix_only: If True, only match prefixes (for autocomplete)

    Returns:
        SQLAlchemy query condition
    """
    # Escape the value for LIKE pattern
    escaped_value = escape_sql_like(value)

    # Create parameterized query
    if prefix_only:
        return field.ilike(f"{escaped_value}%")
    else:
        return field.ilike(f"%{escaped_value}%")


def validate_request_size(max_size: int = 1024 * 1024) -> callable:
    """
    Decorator to validate request size

    Args:
        max_size: Maximum request size in bytes

    Returns:
        Decorator function
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.content_length and request.content_length > max_size:
                return jsonify({"error": "Request too large"}), 413
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def validate_query_params(required_params: Optional[List[str]] = None) -> callable:
    """
    Decorator to validate query parameters

    Args:
        required_params: List of required parameter names

    Returns:
        Decorator function
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Check required parameters
                if required_params:
                    for param in required_params:
                        if not request.args.get(param):
                            return jsonify({"error": f"Missing required parameter: {param}"}), 400

                # Validate search query if present
                if "q" in request.args:
                    query = request.args.get("q", "").strip()
                    if query:
                        validate_search_query(query)

                # Validate filter parameters
                for field in ALLOWED_FILTER_FIELDS:
                    if field in request.args:
                        filter_value = request.args.get(field, "").strip()
                        if filter_value:
                            validate_filter_value(filter_value, field)

                # Validate sort parameter
                if "sort" in request.args:
                    sort_value = request.args.get("sort", "").strip()
                    if sort_value:
                        validate_sort_parameter(sort_value)

                # Validate pagination
                if "page" in request.args or "per_page" in request.args:
                    page = request.args.get("page", 1)
                    per_page = request.args.get("per_page", 20)
                    validate_pagination_params(page, per_page)

                return f(*args, **kwargs)

            except ValueError as e:
                logger.warning(f"Parameter validation error: {e}")
                return jsonify({"error": str(e)}), 400

        return decorated_function

    return decorator


def create_safe_bindparam(name: str, value: Any, type_: Any = None) -> Any:
    """
    Create a safe bind parameter for SQL queries

    Args:
        name: Parameter name
        value: Parameter value
        type_: SQLAlchemy type (optional)

    Returns:
        SQLAlchemy bindparam object
    """
    if type_ is None:
        if isinstance(value, str):
            type_ = String
        elif isinstance(value, int):
            type_ = Integer

    return bindparam(name, value, type_=type_)


def log_security_event(event_type: str, details: Dict[str, Any]) -> None:
    """
    Log security-related events

    Args:
        event_type: Type of security event
        details: Event details
    """
    logger.warning(f"Security event: {event_type} - {details}")
