"""HTTP Bearer token extraction middleware and session helpers.

Inspects incoming HTTP connection headers and resolves tokens to verified roles.
"""
from typing import Any
from twin_interface.auth import resolve_token


def extract_bearer_token(headers: dict[str, str] | Any) -> str | None:
    """Extract Bearer token string from an HTTP headers mapping or dictionary.

    Args:
        headers: A dictionary or mapping of HTTP headers (case-insensitive search).

    Returns:
        The extracted token string, or None if missing or malformed.
    """
    if not headers:
        return None

    # Handle Starlette / case-insensitive header mappings
    auth_header = None
    if hasattr(headers, "get"):
        auth_header = headers.get("authorization") or headers.get("Authorization")

    if not auth_header or not isinstance(auth_header, str):
        return None

    cleaned = auth_header.strip()
    if cleaned.lower().startswith("bearer "):
        return cleaned[7:].strip()

    return cleaned


def resolve_header_role(headers: dict[str, str] | Any) -> str | None:
    """Extract token from headers and resolve to authorized role.

    Args:
        headers: Inbound HTTP headers mapping.

    Returns:
        Role string (e.g. 'brain', 'guardian') or None if unauthenticated.
    """
    token = extract_bearer_token(headers)
    return resolve_token(token)
