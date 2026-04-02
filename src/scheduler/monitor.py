
import datetime
import time
from typing import Dict
from collections import deque
from .models import Request, LoadMetrics, calculate_token_consumption


class SlidingWindowCounter:
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._entries = deque()
        self._last_cleanup_time = 0
        self._cleanup_interval = 5  # 每5秒清理一次

    def _cleanup(self, current_time: float = None):
        if current_time is None:
            current_time = time.time()
        # 限制清理频率，避免频繁清理
        if current_time - self._last_cleanup_time < self._cleanup_interval:
            return
        
        cutoff = current_time - self.window_seconds
        while self._entries and self._entries[0][0] < cutoff:
            self._entries.popleft()
        self._last_cleanup_time = current_time

    def increment(self, value: int = 1, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        # 只在必要时清理
        if len(self._entries) > 100:  # 当条目超过100时清理
            self._cleanup(timestamp)
        self._entries.append((timestamp, value))

    def get_count(self) -> int:
        # 强制清理，确保过期条目被移除
        current_time = time.time()
        cutoff = current_time - self.window_seconds
        while self._entries and self._entries[0][0] < cutoff:
            self._entries.popleft()
        self._last_cleanup_time = current_time
        return sum(value for _, value in self._entries)


class ResourceMonitor:
    def __init__(self):
        self.total_qpm_counter = SlidingWindowCounter(60)
        self.total_tpm_counter = SlidingWindowCounter(60)
        self.scene_qpm_counters: Dict[str, SlidingWindowCounter] = {}
        self.scene_tpm_counters: Dict[str, SlidingWindowCounter] = {}
        self._last_cleanup_time = 0
        self._cleanup_interval = 10  # 每10秒清理一次场景计数器

    def _cleanup_scene_counters(self):
        """清理长时间未使用的场景计数器"""
        current_time = time.time()
        if current_time - self._last_cleanup_time < self._cleanup_interval:
            return
        
        # 找出长时间未使用的场景（10分钟无活动）
        inactive_scenes = []
        cutoff = current_time - 600  # 10分钟
        
        for scene_id, counter in self.scene_qpm_counters.items():
            # 检查计数器是否为空或最后活动时间超过10分钟
            if not counter._entries or counter._entries[-1][0] < cutoff:
                inactive_scenes.append(scene_id)
        
        # 删除不活跃的场景计数器
        for scene_id in inactive_scenes:
            if scene_id in self.scene_qpm_counters:
                del self.scene_qpm_counters[scene_id]
            if scene_id in self.scene_tpm_counters:
                del self.scene_tpm_counters[scene_id]
        
        self._last_cleanup_time = current_time

    def record_request(self, request: Request):
        token_consumption = calculate_token_consumption(request)
        self.total_qpm_counter.increment(1)
        self.total_tpm_counter.increment(token_consumption)
        
        # 只在场景不存在时创建新计数器
        if request.scene_id not in self.scene_qpm_counters:
            self.scene_qpm_counters[request.scene_id] = SlidingWindowCounter(60)
        if request.scene_id not in self.scene_tpm_counters:
            self.scene_tpm_counters[request.scene_id] = SlidingWindowCounter(60)
        
        self.scene_qpm_counters[request.scene_id].increment(1)
        self.scene_tpm_counters[request.scene_id].increment(token_consumption)
        
        # 定期清理不活跃的场景计数器
        if len(self.scene_qpm_counters) > 10:
            self._cleanup_scene_counters()

    def get_total_load(self) -> LoadMetrics:
        return LoadMetrics(
            qpm=self.total_qpm_counter.get_count(),
            tpm=self.total_tpm_counter.get_count()
        )

    def get_scene_load(self, scene_id: str) -> LoadMetrics:
        # 使用get方法，避免创建临时对象
        qpm_counter = self.scene_qpm_counters.get(scene_id)
        tpm_counter = self.scene_tpm_counters.get(scene_id)
        
        qpm = qpm_counter.get_count() if qpm_counter else 0
        tpm = tpm_counter.get_count() if tpm_counter else 0
        
        return LoadMetrics(qpm=qpm, tpm=tpm)

    def get_all_scenes_load(self) -> Dict[str, LoadMetrics]:
        result = {}
        # 清理不活跃的场景计数器
        self._cleanup_scene_counters()
        
        for scene_id in list(self.scene_qpm_counters.keys()):
            result[scene_id] = self.get_scene_load(scene_id)
        return result

