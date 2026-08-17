"""popmely local data dashboard (read-only view over ~/.popmely/popmely.db)."""

from popmely.dashboard.queries import collect

__all__ = ["collect"]
