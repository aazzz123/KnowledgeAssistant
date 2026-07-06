import threading
from typing import Dict, Optional

from cache.redis_cache import redis_cache
from config import REVIEW_TASK_TTL_SECONDS
from models.schemas import TaskState


class ReviewStore:
    """Task store for pending review and finalized answers."""

    def __init__(self):
        self._items: Dict[str, TaskState] = {}
        self._lock = threading.Lock()

    def create(self, task: TaskState) -> TaskState:
        with self._lock:
            self._items[task.task_id] = task
            redis_cache.set_json(
                self._key(task.task_id),
                task.model_dump(),
                ttl_seconds=REVIEW_TASK_TTL_SECONDS,
            )
        return task

    def get(self, task_id: str) -> Optional[TaskState]:
        cached = redis_cache.get_json(self._key(task_id))
        if cached:
            task = TaskState(**cached)
            self._items[task_id] = task
            return task
        return self._items.get(task_id)

    def update(self, task: TaskState) -> TaskState:
        with self._lock:
            self._items[task.task_id] = task
            redis_cache.set_json(
                self._key(task.task_id),
                task.model_dump(),
                ttl_seconds=REVIEW_TASK_TTL_SECONDS,
            )
        return task

    def _key(self, task_id: str) -> str:
        return f"review_task:{task_id}"
