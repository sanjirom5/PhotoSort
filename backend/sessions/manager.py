import uuid
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum


class SessionStatus(str, Enum):
    COLLECTING = "collecting"
    SORTING = "sorting"
    DONE = "done"
    ERROR = "error"


@dataclass
class ClusterInfo:
    cluster_id: str
    label: str
    photo_ids: List[str] = field(default_factory=list)


@dataclass
class SortResults:
    people: List[ClusterInfo] = field(default_factory=list)
    scenes: Dict[str, List[str]] = field(default_factory=dict)
    uncategorized: List[str] = field(default_factory=list)
    output_folder_id: Optional[str] = None
    output_folder_link: Optional[str] = None


@dataclass
class Session:
    id: str
    drive_folder_id: str
    drive_folder_link: str
    telegram_link: str
    photo_count: int = 0
    status: SessionStatus = SessionStatus.COLLECTING
    results: Optional[SortResults] = None
    created_at: float = field(default_factory=time.time)
    error: Optional[str] = None
    telegram_users: Dict[int, bool] = field(default_factory=dict)


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def create(self, drive_folder_id: str, drive_folder_link: str, bot_username: str) -> Session:
        session_id = str(uuid.uuid4()).replace("-", "")[:8].upper()
        telegram_link = f"https://t.me/{bot_username}?start={session_id}"
        session = Session(
            id=session_id,
            drive_folder_id=drive_folder_id,
            drive_folder_link=drive_folder_link,
            telegram_link=telegram_link,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id.upper())

    def update_photo_count(self, session_id: str, count: int):
        s = self.get(session_id)
        if s:
            s.photo_count = count

    def set_status(
        self,
        session_id: str,
        status: SessionStatus,
        results: Optional[SortResults] = None,
        error: Optional[str] = None,
    ):
        s = self.get(session_id)
        if s:
            s.status = status
            if results is not None:
                s.results = results
            if error is not None:
                s.error = error

    def add_telegram_user(self, session_id: str, user_id: int):
        s = self.get(session_id)
        if s:
            s.telegram_users[user_id] = True

    def rename_cluster(self, session_id: str, old_label: str, new_label: str) -> bool:
        s = self.get(session_id)
        if not s or not s.results:
            return False
        for cluster in s.results.people:
            if cluster.label.lower() == old_label.lower() or cluster.cluster_id == old_label:
                cluster.label = new_label
                return True
        return False
