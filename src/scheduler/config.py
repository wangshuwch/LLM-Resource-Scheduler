from typing import Dict, Optional, List, Callable
import threading
from .models import Scene


class SceneConfigManager:
    def __init__(self):
        self.scenes: Dict[str, Scene] = {}
        self._lock = threading.RLock()  # 使用可重入锁
        self._observers: List[Callable[[str, Scene], None]] = []

    def validate_scene(self, scene: Scene) -> bool:
        """验证场景配置的合法性"""
        if not scene.scene_id or not scene.scene_id.strip():
            return False
        if scene.priority < 1 or scene.priority > 10:
            return False
        if scene.max_qpm < 0:
            return False
        if scene.max_tpm < 0:
            return False
        return True

    def add_observer(self, observer: Callable[[str, Scene], None]) -> None:
        """添加配置变更观察者"""
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)

    def remove_observer(self, observer: Callable[[str, Scene], None]) -> None:
        """移除配置变更观察者"""
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def _notify_observers(self, scene_id: str, scene: Scene) -> None:
        """通知所有观察者配置变更"""
        with self._lock:
            observers = self._observers.copy()
        # 释放锁后再通知，避免死锁
        for observer in observers:
            try:
                observer(scene_id, scene)
            except Exception:
                # 忽略观察者执行异常，确保系统稳定性
                pass

    def add_or_update_scene(self, scene: Scene) -> bool:
        """创建或更新场景配置"""
        if not self.validate_scene(scene):
            return False
        with self._lock:
            self.scenes[scene.scene_id] = scene
        # 通知观察者配置变更
        self._notify_observers(scene.scene_id, scene)
        return True

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        """获取场景配置"""
        with self._lock:
            return self.scenes.get(scene_id)

    def get_all_scenes(self) -> Dict[str, Scene]:
        """获取所有场景配置"""
        with self._lock:
            return self.scenes.copy()

    def delete_scene(self, scene_id: str) -> bool:
        """删除场景配置"""
        scene = None
        with self._lock:
            if scene_id in self.scenes:
                scene = self.scenes[scene_id]
                del self.scenes[scene_id]
        if scene:
            # 通知观察者配置变更
            self._notify_observers(scene_id, scene)
            return True
        return False

    def update_scene_priority(self, scene_id: str, priority: int) -> bool:
        """更新场景优先级"""
        with self._lock:
            if scene_id not in self.scenes:
                return False
            # 先验证优先级是否合法
            if priority < 1 or priority > 10:
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
            except Exception:
                return False
            self.scenes[scene_id] = updated_scene
        # 通知观察者配置变更
        self._notify_observers(scene_id, updated_scene)
        return True

    def update_scene_limits(self, scene_id: str, max_qpm: int, max_tpm: int) -> bool:
        """更新场景资源限制"""
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
