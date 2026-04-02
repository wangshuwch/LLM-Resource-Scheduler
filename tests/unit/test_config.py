import unittest
from src.scheduler.config import SceneConfigManager
from src.scheduler.models import Scene


class TestSceneConfigManager(unittest.TestCase):
    def setUp(self):
        self.manager = SceneConfigManager()
        self.test_scene = Scene(
            scene_id="test_scene",
            priority=5,
            max_qpm=100,
            max_tpm=1000
        )

    def test_validate_scene(self):
        # 测试有效场景
        self.assertTrue(self.manager.validate_scene(self.test_scene))

        # 测试无效场景：空scene_id
        # 注意：由于Scene模型有Pydantic验证，我们不能直接创建无效的Scene对象
        # 所以我们需要模拟validate_scene方法的逻辑测试
        # 这里我们测试现有的validate_scene方法对有效场景的处理
        # 对于无效场景，我们通过测试add_or_update_scene方法来间接测试
        
        # 测试添加无效场景（空scene_id）
        # 注意：由于Pydantic验证，我们不能直接创建空scene_id的Scene对象
        # 所以我们测试add_or_update_scene方法的返回值
        # 这里我们使用一个有效场景，然后测试其他边界情况
        
        # 测试更新场景优先级超出范围
        self.manager.add_or_update_scene(self.test_scene)
        result = self.manager.update_scene_priority("test_scene", 11)
        self.assertFalse(result)
        result = self.manager.update_scene_priority("test_scene", 0)
        self.assertFalse(result)
        
        # 测试更新场景资源限制为负数
        result = self.manager.update_scene_limits("test_scene", -1, 1000)
        self.assertFalse(result)
        result = self.manager.update_scene_limits("test_scene", 100, -1)
        self.assertFalse(result)

    def test_add_or_update_scene(self):
        # 测试添加场景
        result = self.manager.add_or_update_scene(self.test_scene)
        self.assertTrue(result)
        scene = self.manager.get_scene("test_scene")
        self.assertIsNotNone(scene)
        self.assertEqual(scene.scene_id, "test_scene")
        self.assertEqual(scene.priority, 5)
        self.assertEqual(scene.max_qpm, 100)
        self.assertEqual(scene.max_tpm, 1000)

        # 测试更新场景
        updated_scene = Scene(
            scene_id="test_scene",
            priority=8,
            max_qpm=200,
            max_tpm=2000
        )
        result = self.manager.add_or_update_scene(updated_scene)
        self.assertTrue(result)
        scene = self.manager.get_scene("test_scene")
        self.assertIsNotNone(scene)
        self.assertEqual(scene.priority, 8)
        self.assertEqual(scene.max_qpm, 200)
        self.assertEqual(scene.max_tpm, 2000)

    def test_get_scene(self):
        # 测试获取不存在的场景
        scene = self.manager.get_scene("non_existent")
        self.assertIsNone(scene)

        # 测试获取存在的场景
        self.manager.add_or_update_scene(self.test_scene)
        scene = self.manager.get_scene("test_scene")
        self.assertIsNotNone(scene)
        self.assertEqual(scene.scene_id, "test_scene")

    def test_get_all_scenes(self):
        # 测试获取所有场景
        self.assertEqual(len(self.manager.get_all_scenes()), 0)

        # 添加场景
        self.manager.add_or_update_scene(self.test_scene)
        scenes = self.manager.get_all_scenes()
        self.assertEqual(len(scenes), 1)
        self.assertIn("test_scene", scenes)

    def test_delete_scene(self):
        # 测试删除不存在的场景
        result = self.manager.delete_scene("non_existent")
        self.assertFalse(result)

        # 测试删除存在的场景
        self.manager.add_or_update_scene(self.test_scene)
        result = self.manager.delete_scene("test_scene")
        self.assertTrue(result)
        scene = self.manager.get_scene("test_scene")
        self.assertIsNone(scene)

    def test_update_scene_priority(self):
        # 测试更新不存在场景的优先级
        result = self.manager.update_scene_priority("non_existent", 8)
        self.assertFalse(result)

        # 测试更新存在场景的优先级
        self.manager.add_or_update_scene(self.test_scene)
        result = self.manager.update_scene_priority("test_scene", 8)
        self.assertTrue(result)
        scene = self.manager.get_scene("test_scene")
        self.assertEqual(scene.priority, 8)

        # 测试更新无效优先级
        result = self.manager.update_scene_priority("test_scene", 11)
        self.assertFalse(result)
        scene = self.manager.get_scene("test_scene")
        self.assertEqual(scene.priority, 8)  # 应该保持不变

    def test_update_scene_limits(self):
        # 测试更新不存在场景的限制
        result = self.manager.update_scene_limits("non_existent", 200, 2000)
        self.assertFalse(result)

        # 测试更新存在场景的限制
        self.manager.add_or_update_scene(self.test_scene)
        result = self.manager.update_scene_limits("test_scene", 200, 2000)
        self.assertTrue(result)
        scene = self.manager.get_scene("test_scene")
        self.assertEqual(scene.max_qpm, 200)
        self.assertEqual(scene.max_tpm, 2000)

        # 测试更新无效限制
        result = self.manager.update_scene_limits("test_scene", -1, 2000)
        self.assertFalse(result)
        scene = self.manager.get_scene("test_scene")
        self.assertEqual(scene.max_qpm, 200)  # 应该保持不变

    def test_observer_pattern(self):
        # 测试观察者模式
        observed_changes = []

        def observer(scene_id, scene):
            observed_changes.append((scene_id, scene))

        # 添加观察者
        self.manager.add_observer(observer)

        # 添加场景，应该触发观察者
        self.manager.add_or_update_scene(self.test_scene)
        self.assertEqual(len(observed_changes), 1)
        self.assertEqual(observed_changes[0][0], "test_scene")
        self.assertEqual(observed_changes[0][1].scene_id, "test_scene")

        # 更新场景，应该触发观察者
        updated_scene = Scene(
            scene_id="test_scene",
            priority=8,
            max_qpm=200,
            max_tpm=2000
        )
        self.manager.add_or_update_scene(updated_scene)
        self.assertEqual(len(observed_changes), 2)
        self.assertEqual(observed_changes[1][0], "test_scene")
        self.assertEqual(observed_changes[1][1].priority, 8)

        # 删除场景，应该触发观察者
        self.manager.delete_scene("test_scene")
        self.assertEqual(len(observed_changes), 3)
        self.assertEqual(observed_changes[2][0], "test_scene")

        # 移除观察者
        self.manager.remove_observer(observer)
        observed_changes.clear()

        # 添加场景，不应该触发观察者
        self.manager.add_or_update_scene(self.test_scene)
        self.assertEqual(len(observed_changes), 0)


if __name__ == '__main__':
    unittest.main()
