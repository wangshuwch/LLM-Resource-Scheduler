
import datetime
import time
from typing import Dict
from collections import deque
from .models import Request, LoadMetrics, calculate_token_consumption


class SlidingWindowCounter:
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._entries = deque()

    def _cleanup(self, current_time: float = None):
        if current_time is None:
            current_time = time.time()
        cutoff = current_time - self.window_seconds
        while self._entries and self._entries[0][0] < cutoff:
            self._entries.popleft()

    def increment(self, value: int = 1, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        self._cleanup(timestamp)
        self._entries.append((timestamp, value))

    def get_count(self) -> int:
        self._cleanup()
        return sum(value for _, value in self._entries)


class ResourceMonitor:
    def __init__(self):
        self.total_qpm_counter = SlidingWindowCounter(60)
        self.total_tpm_counter = SlidingWindowCounter(60)
        self.scene_qpm_counters: Dict[str, SlidingWindowCounter] = {}
        self.scene_tpm_counters: Dict[str, SlidingWindowCounter] = {}

    def record_request(self, request: Request):
        token_consumption = calculate_token_consumption(request)
        self.total_qpm_counter.increment(1)
        self.total_tpm_counter.increment(token_consumption)
        if request.scene_id not in self.scene_qpm_counters:
            self.scene_qpm_counters[request.scene_id] = SlidingWindowCounter(60)
        if request.scene_id not in self.scene_tpm_counters:
            self.scene_tpm_counters[request.scene_id] = SlidingWindowCounter(60)
        self.scene_qpm_counters[request.scene_id].increment(1)
        self.scene_tpm_counters[request.scene_id].increment(token_consumption)

    def get_total_load(self) -> LoadMetrics:
        return LoadMetrics(
            qpm=self.total_qpm_counter.get_count(),
            tpm=self.total_tpm_counter.get_count()
        )

    def get_scene_load(self, scene_id: str) -> LoadMetrics:
        qpm = self.scene_qpm_counters.get(scene_id, SlidingWindowCounter(60)).get_count()
        tpm = self.scene_tpm_counters.get(scene_id, SlidingWindowCounter(60)).get_count()
        return LoadMetrics(qpm=qpm, tpm=tpm)

    def get_all_scenes_load(self) -> Dict[str, LoadMetrics]:
        result = {}
        for scene_id in self.scene_qpm_counters.keys():
            result[scene_id] = self.get_scene_load(scene_id)
        return result

