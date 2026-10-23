"""Allow-list data projections to prevent Ground Truth leakage.

Enforces strict information boundaries: the Brain and Guardian receive only
observed values and public statuses. Secret simulation variables (actual_value,
delta, fault) are stripped unless the caller is the Evaluator (Jury).
"""
from typing import Any
from twin_interface.auth import Role

# Strict whitelist of fields that public layers (Brain and Guardian) are permitted to see
PUBLIC_READING_ALLOWLIST = frozenset({
    "sensor_id",
    "zone_id",
    "type",
    "unit",
    "timestamp",
    "sim_tick",
    "seq",
    "reported_value",
    "status",
    "available",
    "backup_ids",
    "linked_device_ids",
})

# Forbidden ground-truth fields that must NEVER appear in Brain or Guardian responses
FORBIDDEN_TRUTH_FIELDS = frozenset({
    "actual_value",
    "delta",
    "fault",
    "noise",
    "drift_rate",
    "lag_ticks",
    "bias",
    "ground_truth",
})


def project_reading(reading: dict[str, Any], role: str) -> dict[str, Any]:
    """Sanitize a single sensor reading dictionary based on the caller's role.

    Args:
        reading: Raw sensor reading dictionary from the simulation.
        role: Verified role of the caller (from Role).

    Returns:
        Sanitized dictionary with private ground-truth fields removed for public roles.
    """
    if role == Role.EVALUATOR:
        # The Evaluator/Jury role is explicitly granted full access to verify truth
        return dict(reading)

    # Brain, Guardian, and Operator receive ONLY allow-listed fields
    projected = {k: v for k, v in reading.items() if k in PUBLIC_READING_ALLOWLIST}

    # Defensive guarantee: Ensure none of the forbidden fields exist in output
    for forbidden in FORBIDDEN_TRUTH_FIELDS:
        projected.pop(forbidden, None)

    return projected


def project_readings(readings: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    """Sanitize a list of sensor reading dictionaries."""
    return [project_reading(r, role) for r in readings]


def project_event(event: dict[str, Any], role: str) -> dict[str, Any]:
    """Sanitize an event dictionary before it is published to the public event log."""
    if role == Role.EVALUATOR:
        return dict(event)

    sanitized = dict(event)
    details = sanitized.get("details")
    if isinstance(details, dict):
        sanitized["details"] = {k: v for k, v in details.items() if k not in FORBIDDEN_TRUTH_FIELDS}

    return sanitized
