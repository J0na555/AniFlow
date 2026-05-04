from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import QuerySet, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.anime.models import UserAnime
from apps.users.models import UserSettings


@dataclass(frozen=True)
class ProductivityStats:
    watching_count: int
    completed_count: int
    completion_rate: float
    weekly_episodes: int


@dataclass(frozen=True)
class WatchingLimitState:
    enabled: bool
    ignored: bool
    limit: int
    watching_count: int
    reached: bool
    remaining_slots: int

    @property
    def message(self) -> str:
        if not self.enabled:
            return "Watching limit is disabled."
        if self.ignored:
            return "Watching limit warnings are currently ignored."
        if self.reached:
            return (
                f"Watching limit reached ({self.watching_count}/{self.limit}). "
                "Finish a title or override the limit to start another one."
            )
        return f"{self.remaining_slots} watching slot(s) remaining."


def _start_of_week():
    today = timezone.localdate()
    return today - timedelta(days=today.weekday())


def _entries_for_user(user) -> QuerySet[UserAnime]:
    return UserAnime.objects.filter(user=user)


def get_productivity_stats(user, *, entries: QuerySet[UserAnime] | None = None) -> ProductivityStats:
    base_entries = entries if entries is not None else _entries_for_user(user)
    watching_count = base_entries.filter(status="watching").count()
    completed_count = base_entries.filter(status="completed").count()
    started_count = base_entries.exclude(status="planning").count()
    completion_rate = round((completed_count / started_count) * 100, 1) if started_count else 0.0
    weekly_episodes = (
        base_entries.filter(updated_at__date__gte=_start_of_week())
        .aggregate(total=Coalesce(Sum("progress"), 0))
        .get("total", 0)
    )
    return ProductivityStats(
        watching_count=watching_count,
        completed_count=completed_count,
        completion_rate=completion_rate,
        weekly_episodes=int(weekly_episodes or 0),
    )


def get_watching_limit_state(
    user,
    *,
    watching_count: int | None = None,
    settings: UserSettings | None = None,
) -> WatchingLimitState:
    user_settings = settings or UserSettings.objects.get_or_create(user=user)[0]
    active_watching = (
        watching_count
        if watching_count is not None
        else _entries_for_user(user).filter(status="watching").count()
    )
    limit = user_settings.max_watching_limit
    enabled = limit > 0
    ignored = user_settings.ignore_watching_limit
    reached = enabled and not ignored and active_watching >= limit
    remaining_slots = max(limit - active_watching, 0) if enabled else 0
    return WatchingLimitState(
        enabled=enabled,
        ignored=ignored,
        limit=limit,
        watching_count=active_watching,
        reached=reached,
        remaining_slots=remaining_slots,
    )


def enable_watching_limit_override(user) -> UserSettings:
    settings, _ = UserSettings.objects.get_or_create(user=user)
    if not settings.ignore_watching_limit:
        settings.ignore_watching_limit = True
        settings.save(update_fields=["ignore_watching_limit", "updated_at"])
    return settings
