"""Data models for authentication context and role-based access control."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Role(IntEnum):
    """Hierarchical access level.  Higher numeric value = more privileges.

    Using IntEnum allows simple ``>=`` comparisons for role checks:
    ``Role.USER >= Role.GUEST`` is ``True``.
    """

    GUEST = 0
    USER = 1
    CREATOR = 2


@dataclass(frozen=True)
class AuthContext:
    """Resolved identity and role for the current request."""

    role: Role
    email: str | None = None
    name: str | None = None

    @property
    def authenticated(self) -> bool:
        """Whether the request carries a verified identity (email or user name present)."""
        return self.email is not None or (self.name is not None and self.name != 'Host')

    def has_role(self, min_role: Role) -> bool:
        """Return ``True`` if this context meets or exceeds *min_role*."""
        return self.role >= min_role

    @property
    def role_label(self) -> str:
        """Human-readable lowercase label for the resolved role."""
        return self.role.name.lower()
