"""资源监控模块。

本模块提供了基于滑动窗口的资源监控功能，用于跟踪QPM（每分钟查询数）
和TPM（每分钟Token数）的使用情况。

主要功能:
    - 滑动窗口计数器实现
    - 全局资源监控
    - 场景级别资源监控
    - 自动清理过期数据
"""

import datetime
import logging
import time
from typing import Dict, Optional, Deque, Tuple
from collections import deque
from .models import Request, LoadMetrics, calculate_token_consumption

logger = logging.getLogger(__name__)


class SlidingWindowCounter:
    """滑动窗口计数器，用于统计时间窗口内的数据。

    该计数器使用双端队列存储时间戳和值，支持高效的增量统计
    和过期数据清理。

    Attributes:
        window_seconds: 时间窗口大小（秒）。
        _entries: 存储时间戳和值的双端队列。
        _last_cleanup_time: 上次清理时间。
        _cleanup_interval: 清理间隔（秒）。

    Example:
        >>> counter = SlidingWindowCounter(window_seconds=60)
        >>> counter.increment(1)
        >>> counter.increment(5)
        >>> count = counter.get_count()  # 获取最近60秒内的总和
    """

    def __init__(self, window_seconds: int = 60) -> None:
        """初始化滑动窗口计数器。

        Args:
            window_seconds: 时间窗口大小（秒），默认为60秒。
        """
        self.window_seconds: int = window_seconds
        self._entries: Deque[Tuple[float, int]] = deque()
        self._last_cleanup_time: float = 0
        self._cleanup_interval: int = 5

    def _cleanup(self, current_time: Optional[float] = None) -> None:
        """清理过期的数据条目。

        移除时间戳超出窗口范围的条目，并更新上次清理时间。

        Args:
            current_time: 当前时间戳，如果未提供则使用time.time()。

        Note:
            这是内部方法，会在increment和get_count时自动调用。
        """
        if current_time is None:
            current_time = time.time()
        if current_time - self._last_cleanup_time < self._cleanup_interval:
            return
        
        cutoff = current_time - self.window_seconds
        while self._entries and self._entries[0][0] < cutoff:
            self._entries.popleft()
        self._last_cleanup_time = current_time

    def increment(self, value: int = 1, timestamp: Optional[float] = None) -> None:
        """增加一个数据条目。

        将指定值和时间戳添加到计数器中。当条目数量超过100时
        会自动触发清理。

        Args:
            value: 要增加的值，默认为1。
            timestamp: 时间戳，如果未提供则使用当前时间。

        Example:
            >>> counter.increment(10)  # 增加10
            >>> counter.increment(5, timestamp=time.time() - 30)  # 30秒前增加5
        """
        if timestamp is None:
            timestamp = time.time()
        if len(self._entries) > 100:
            self._cleanup(timestamp)
        self._entries.append((timestamp, value))

    def get_count(self) -> int:
        """获取时间窗口内的数据总和。

        清理过期数据后，返回窗口内所有条目的值总和。

        Returns:
            时间窗口内所有值的总和。

        Example:
            >>> counter.increment(10)
            >>> counter.increment(20)
            >>> total = counter.get_count()  # 返回30
        """
        current_time = time.time()
        cutoff = current_time - self.window_seconds
        while self._entries and self._entries[0][0] < cutoff:
            self._entries.popleft()
        self._last_cleanup_time = current_time
        return sum(value for _, value in self._entries)


class ResourceMonitor:
    """资源监控器，跟踪全局和场景级别的资源使用情况。

    该监控器使用滑动窗口计数器跟踪QPM和TPM，支持全局统计
    和按场景分别统计。

    Attributes:
        total_qpm_counter: 全局QPM计数器。
        total_tpm_counter: 全局TPM计数器。
        scene_qpm_counters: 场景QPM计数器字典。
        scene_tpm_counters: 场景TPM计数器字典。
        _last_cleanup_time: 上次清理时间。
        _cleanup_interval: 清理间隔（秒）。

    Example:
        >>> monitor = ResourceMonitor()
        >>> request = Request(scene_id="chat", prompt="Hello", max_output_token=100)
        >>> monitor.record_request(request)
        >>> load = monitor.get_total_load()
        >>> print(f"QPM: {load.qpm}, TPM: {load.tpm}")
    """

    def __init__(self) -> None:
        """初始化资源监控器。"""
        self.total_qpm_counter: SlidingWindowCounter = SlidingWindowCounter(60)
        self.total_tpm_counter: SlidingWindowCounter = SlidingWindowCounter(60)
        self.scene_qpm_counters: Dict[str, SlidingWindowCounter] = {}
        self.scene_tpm_counters: Dict[str, SlidingWindowCounter] = {}
        self._last_cleanup_time: float = 0
        self._cleanup_interval: int = 10

    def _cleanup_scene_counters(self) -> None:
        """清理不活跃的场景计数器。

        移除超过600秒没有活动的场景计数器，释放内存。

        Note:
            这是内部方法，在record_request时自动调用。
        """
        current_time = time.time()
        if current_time - self._last_cleanup_time < self._cleanup_interval:
            return
        
        inactive_scenes: list[str] = []
        cutoff = current_time - 600
        
        for scene_id, counter in self.scene_qpm_counters.items():
            if not counter._entries or counter._entries[-1][0] < cutoff:
                inactive_scenes.append(scene_id)
        
        for scene_id in inactive_scenes:
            if scene_id in self.scene_qpm_counters:
                del self.scene_qpm_counters[scene_id]
            if scene_id in self.scene_tpm_counters:
                del self.scene_tpm_counters[scene_id]
        
        if inactive_scenes:
            logger.debug(f"Cleaned up {len(inactive_scenes)} inactive scene counters: {inactive_scenes}")
        
        self._last_cleanup_time = current_time

    def record_request(self, request: Request) -> None:
        """记录一个请求的资源使用情况。

        更新全局和场景级别的QPM和TPM计数器。

        Args:
            request: 已处理的请求对象。

        Example:
            >>> request = Request(scene_id="chat", prompt="Hello", max_output_token=100)
            >>> monitor.record_request(request)
        """
        token_consumption = calculate_token_consumption(request)
        self.total_qpm_counter.increment(1)
        self.total_tpm_counter.increment(token_consumption)
        
        if request.scene_id not in self.scene_qpm_counters:
            self.scene_qpm_counters[request.scene_id] = SlidingWindowCounter(60)
        if request.scene_id not in self.scene_tpm_counters:
            self.scene_tpm_counters[request.scene_id] = SlidingWindowCounter(60)
        
        self.scene_qpm_counters[request.scene_id].increment(1)
        self.scene_tpm_counters[request.scene_id].increment(token_consumption)
        
        logger.debug(f"Recorded request: scene_id={request.scene_id}, token_consumption={token_consumption}")
        
        if len(self.scene_qpm_counters) > 10:
            self._cleanup_scene_counters()

    def get_total_load(self) -> LoadMetrics:
        """获取全局资源负载。

        Returns:
            包含全局QPM和TPM的LoadMetrics对象。

        Example:
            >>> load = monitor.get_total_load()
            >>> print(f"Global QPM: {load.qpm}, TPM: {load.tpm}")
        """
        return LoadMetrics(
            qpm=self.total_qpm_counter.get_count(),
            tpm=self.total_tpm_counter.get_count()
        )

    def get_scene_load(self, scene_id: str) -> LoadMetrics:
        """获取指定场景的资源负载。

        Args:
            scene_id: 场景ID。

        Returns:
            包含该场景QPM和TPM的LoadMetrics对象。
            如果场景不存在，返回QPM和TPM都为0的LoadMetrics。

        Example:
            >>> load = monitor.get_scene_load("chat")
            >>> print(f"Scene QPM: {load.qpm}, TPM: {load.tpm}")
        """
        qpm_counter = self.scene_qpm_counters.get(scene_id)
        tpm_counter = self.scene_tpm_counters.get(scene_id)
        
        qpm = qpm_counter.get_count() if qpm_counter else 0
        tpm = tpm_counter.get_count() if tpm_counter else 0
        
        return LoadMetrics(qpm=qpm, tpm=tpm)

    def get_all_scenes_load(self) -> Dict[str, LoadMetrics]:
        """获取所有场景的资源负载。

        在返回结果前会清理不活跃的场景计数器。

        Returns:
            场景负载字典，键为场景ID，值为LoadMetrics对象。

        Example:
            >>> loads = monitor.get_all_scenes_load()
            >>> for scene_id, load in loads.items():
            ...     print(f"{scene_id}: QPM={load.qpm}, TPM={load.tpm}")
        """
        result: Dict[str, LoadMetrics] = {}
        self._cleanup_scene_counters()
        
        for scene_id in list(self.scene_qpm_counters.keys()):
            result[scene_id] = self.get_scene_load(scene_id)
        return result

