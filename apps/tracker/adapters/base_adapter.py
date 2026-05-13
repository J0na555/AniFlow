from abc import ABC, abstractmethod

from django.contrib.auth import get_user_model

User = get_user_model()


class TrackerAdapter(ABC):
    @abstractmethod
    def get_user_list(self, user: User) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def update_progress(self, user: User, tracker_id: str, progress: int) -> dict:
        raise NotImplementedError

    @abstractmethod
    def search_anime(self, query: str, *, limit: int = 20) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def save_list_entry(
        self,
        user: User,
        tracker_id: str,
        *,
        status: str,
        progress: int | None = None,
        score: float | None = None,
    ) -> dict:
        raise NotImplementedError

    def get_recommendations(self, user, limit: int = 10) -> list[dict]:
        raise NotImplementedError

    def get_weekly_releases(self, user, limit: int = 10) -> list[dict]:
        raise NotImplementedError
