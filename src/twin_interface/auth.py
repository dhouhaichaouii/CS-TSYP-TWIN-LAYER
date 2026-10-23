"""Bearer token authentication and role resolution.

Resolves caller tokens to trusted roles using constant-time comparison
to guard against side-channel timing attacks.
"""
import hmac
import os


class Role:
    """The four official roles in the Twin Layer security perimeter."""
    BRAIN = "brain"
    GUARDIAN = "guardian"
    OPERATOR = "operator"
    EVALUATOR = "evaluator"
    ALL_ROLES = {BRAIN, GUARDIAN, OPERATOR, EVALUATOR}


# Default fallback tokens used for local development/testing when env vars are not set
DEFAULT_TOKENS = {
    Role.BRAIN: "token-brain-secret-2026",
    Role.GUARDIAN: "token-guardian-secret-2026",
    Role.OPERATOR: "token-operator-secret-2026",
    Role.EVALUATOR: "token-evaluator-secret-2026",
}


def get_token_for_role(role: str) -> str:
    """Retrieve the expected bearer token for a role from environment or defaults."""
    env_key = f"TWIN_TOKEN_{role.upper()}"
    return os.environ.get(env_key, DEFAULT_TOKENS.get(role, ""))


def resolve_token(raw_token: str | None) -> str | None:
    """Resolve an incoming bearer token string to a verified role.

    Supports both raw tokens ('token-xyz') and authorization header style ('Bearer token-xyz').
    Uses hmac.compare_digest for constant-time comparison.

    Args:
        raw_token: The token string provided by the caller, or None.

    Returns:
        The matched Role string, or None if authentication failed.
    """
    if not raw_token or not isinstance(raw_token, str):
        return None

    cleaned = raw_token.strip()
    if cleaned.lower().startswith("bearer "):
        cleaned = cleaned[7:].strip()

    if not cleaned:
        return None

    for role in (Role.BRAIN, Role.GUARDIAN, Role.OPERATOR, Role.EVALUATOR):
        expected = get_token_for_role(role)
        if expected and hmac.compare_digest(cleaned, expected):
            return role

    return None
