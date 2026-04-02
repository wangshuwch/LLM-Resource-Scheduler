"""场景配置管理模块。

本模块提供了场景配置的管理功能，包括场景的创建、更新、删除和查询。
支持观察者模式，当配置变更时通知相关组件。

主要功能:
    - 场景配置的CRUD操作
    - 配置合法性验证
    - 配置变更通知机制
    - 线程安全的配置管理
"""

from typing import Dict, Optional, List, Callable
import threading
import logging
from .models import Scene

logger = logging.getLogger(__name__)


class SceneConfigManager:
    """场景配置管理器，管理所有场景的配置信息。

    该类提供了场景配置的增删改查功能，并支持观察者模式，
    当配置发生变更时通知所有注册的观察者。

    Attributes:
        scenes: 场景配置字典，键为场景ID，值为Scene对象。
        _lock: 可重入锁，用于线程安全。
        _observers: 观察者列表，当配置变更时会被通知。

    Example:
        >>> manager = SceneConfigManager()
        >>> scene = Scene(scene_id="chat", priority=5, max_qpm=100, max_tpm=10000)
        >>> manager.add_or_update_scene(scene)
        True
        >>> retrieved = manager.get_scene("chat")
        >>> print(retrieved.priority)
        5
    """

    def __init__(self) -> None:
        """初始化场景配置管理器。"""
        self.scenes: Dict[str, Scene] = {}
        self._lock = threading.RLock()  # 使用可重入锁
        self._observers: List[Callable[[str, Scene], None]] = []

    def validate_scene(self, scene: Scene) -> bool:
        """验证场景配置的合法性。

        检查场景ID是否非空、优先级是否在1-10范围内、
        QPM和TPM限制是否为非负数。

        Args:
            scene: 要验证的场景对象。

        Returns:
            如果配置合法返回True，否则返回False。

        Example:
            >>> scene = Scene(scene_id="test", priority=5, max_qpm=100, max_tpm=10000)
            >>> manager.validate_scene(scene)
            True
        """
        if not scene.scene_id or not scene.scene_id.strip():
            logger.error(f"Scene validation failed: scene_id is empty or whitespace")
            return False
        if scene.priority < 1 or scene.priority > 10:
            logger.error(f"Scene validation failed for {scene.scene_id}: priority {scene.priority} is out of range [1, 10]")
            return False
        if scene.max_qpm < 0:
            logger.error(f"Scene validation failed for {scene.scene_id}: max_qpm {scene.max_qpm} is negative")
            return False
        if scene.max_tpm < 0:
            logger.error(f"Scene validation failed for {scene.scene_id}: max_tpm {scene.max_tpm} is negative")
            return False
        return True

    def add_observer(self, observer: Callable[[str, Scene], None]) -> None:
        """添加配置变更观察者。

        当场景配置发生变更时，观察者会被调用。

        Args:
            observer: 观察者函数，接受场景ID和场景对象作为参数。

        Example:
            >>> def on_scene_change(scene_id: str, scene: Scene):
            ...     print(f"Scene {scene_id} changed")
            >>> manager.add_observer(on_scene_change)
        """
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)

    def remove_observer(self, observer: Callable[[str, Scene], None]) -> None:
        """移除配置变更观察者。

        Args:
            observer: 要移除的观察者函数。

        Example:
            >>> manager.remove_observer(on_scene_change)
        """
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def _notify_observers(self, scene_id: str, scene: Scene) -> None:
        """通知所有观察者配置变更。

        在释放锁后通知观察者，避免死锁风险。
        观察者执行异常会被记录日志，确保系统稳定性。

        Args:
            scene_id: 变更的场景ID。
            scene: 变更后的场景对象。

        Note:
            这是内部方法，在配置变更时自动调用。
        """
        with self._lock:
            observers = self._observers.copy()
        logger.debug(f"Notifying {len(observers)} observers for scene {scene_id}")
        for observer in observers:
            try:
                observer(scene_id, scene)
            except ValueError as e:
                logger.exception(f"Observer {observer.__name__} raised ValueError for scene {scene_id}: {str(e)}")
            except KeyError as e:
                logger.exception(f"Observer {observer.__name__} raised KeyError for scene {scene_id}: {str(e)}")
            except (AttributeError, TypeError) as e:
                logger.exception(f"Observer {observer.__name__} raised type error for scene {scene_id}: {str(e)}")
            except Exception as e:
                logger.exception(f"Observer {observer.__name__} raised unexpected error for scene {scene_id}: {str(e)}")

    def add_or_update_scene(self, scene: Scene) -> bool:
        """创建或更新场景配置。

        如果场景ID已存在则更新配置，否则创建新场景。
        配置变更后会通知所有观察者。

        Args:
            scene: 要添加或更新的场景对象。

        Returns:
            如果操作成功返回True，如果配置验证失败返回False。

        Example:
            >>> scene = Scene(scene_id="chat", priority=8, max_qpm=200, max_tpm=50000)
            >>> manager.add_or_update_scene(scene)
            True
        """
        if not self.validate_scene(scene):
            return False
        with self._lock:
            is_update = scene.scene_id in self.scenes
            self.scenes[scene.scene_id] = scene
        self._notify_observers(scene.scene_id, scene)
        action = "updated" if is_update else "added"
        logger.info(f"Scene {scene.scene_id} {action}: priority={scene.priority}, max_qpm={scene.max_qpm}, max_tpm={scene.max_tpm}")
        return True

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        """获取指定场景的配置。

        Args:
            scene_id: 场景ID。

        Returns:
            场景对象，如果不存在则返回None。

        Example:
            >>> scene = manager.get_scene("chat")
            >>> if scene:
            ...     print(f"Priority: {scene.priority}")
        """
        with self._lock:
            return self.scenes.get(scene_id)

    def get_all_scenes(self) -> Dict[str, Scene]:
        """获取所有场景配置。

        Returns:
            场景配置字典的副本，键为场景ID，值为Scene对象。

        Example:
            >>> scenes = manager.get_all_scenes()
            >>> for scene_id, scene in scenes.items():
            ...     print(f"{scene_id}: priority={scene.priority}")
        """
        with self._lock:
            return self.scenes.copy()

    def delete_scene(self, scene_id: str) -> bool:
        """删除指定场景的配置。

        删除成功后会通知所有观察者。

        Args:
            scene_id: 要删除的场景ID。

        Returns:
            如果删除成功返回True，如果场景不存在返回False。

        Example:
            >>> if manager.delete_scene("old_scene"):
            ...     print("Scene deleted successfully")
        """
        scene = None
        with self._lock:
            if scene_id in self.scenes:
                scene = self.scenes[scene_id]
                del self.scenes[scene_id]
        if scene:
            self._notify_observers(scene_id, scene)
            logger.info(f"Scene {scene_id} deleted: priority={scene.priority}, max_qpm={scene.max_qpm}, max_tpm={scene.max_tpm}")
            return True
        return False

    def update_scene_priority(self, scene_id: str, priority: int) -> bool:
        """更新场景的优先级。

        优先级必须在1-10范围内。更新成功后会通知所有观察者。

        Args:
            scene_id: 场景ID。
            priority: 新的优先级值（1-10）。

        Returns:
            如果更新成功返回True，如果场景不存在或优先级无效返回False。

        Example:
            >>> if manager.update_scene_priority("chat", 9):
            ...     print("Priority updated to 9")
        """
        with self._lock:
            if scene_id not in self.scenes:
                logger.error(f"Cannot update priority: scene {scene_id} not found")
                return False
            # 先验证优先级是否合法
            if priority < 1 or priority > 10:
                logger.error(f"Cannot update priority for scene {scene_id}: priority {priority} is out of range [1, 10]")
                return False
            scene = self.scenes[scene_id]
            # 创建新的Scene对象，保持不可变性
            try:
                updated_scene = Scene(
                    scene_id=scene.scene_id,
                    priority=priority,
                    max_qpm=scene.max_qpm,
                    max_tpm=scene.max_tpm
                )
            except ValueError as e:
                logger.exception(f"Failed to create updated scene for {scene_id} with priority {priority}: {str(e)}")
                return False
            except Exception as e:
                logger.exception(f"Unexpected error creating updated scene for {scene_id}: {str(e)}")
                return False
            self.scenes[scene_id] = updated_scene
        # 通知观察者配置变更
        self._notify_observers(scene_id, updated_scene)
        return True

    def update_scene_limits(self, scene_id: str, max_qpm: int, max_tpm: int) -> bool:
        """更新场景的资源限制。

        QPM和TPM限制必须为非负数。更新成功后会通知所有观察者。

        Args:
            scene_id: 场景ID。
            max_qpm: 新的每分钟查询数限制。
            max_tpm: 新的每分钟Token数限制。

        Returns:
            如果更新成功返回True，如果场景不存在或限制无效返回False。

        Example:
            >>> if manager.update_scene_limits("chat", 300, 100000):
            ...     print("Limits updated")
        """
        with self._lock:
            if scene_id not in self.scenes:
                return False
            # 先验证限制是否合法
            if max_qpm < 0 or max_tpm < 0:
                return False
            scene = self.scenes[scene_id]
            # 创建新的Scene对象，保持不可变性
            try:
                updated_scene = Scene(
                    scene_id=scene.scene_id,
                    priority=scene.priority,
                    max_qpm=max_qpm,
                    max_tpm=max_tpm
                )
            except Exception:
                return False
            self.scenes[scene_id] = updated_scene
        # 通知观察者配置变更
        self._notify_observers(scene_id, updated_scene)
        return True
