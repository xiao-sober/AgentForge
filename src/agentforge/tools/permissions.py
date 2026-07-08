from __future__ import annotations


TOOL_PERMISSION_LEVELS = {"read", "write", "execute", "control", "admin"}


def validate_permission_levels(levels: set[str] | None) -> None:
    unknown = (levels or set()) - TOOL_PERMISSION_LEVELS
    if unknown:
        raise ValueError(f"Unsupported Tool permission level: {', '.join(sorted(unknown))}")


def permission_allowed(permission_level: str, allowed_permission_levels: set[str] | None) -> bool:
    return allowed_permission_levels is None or permission_level in allowed_permission_levels
