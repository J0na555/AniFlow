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

    def search_anime(self, query: str) -> list[dict]:
        raise NotImplementedError
