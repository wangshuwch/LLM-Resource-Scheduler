
import pytest
import time
from src.scheduler.monitor import SlidingWindowCounter, ResourceMonitor
from src.scheduler.models import Request, LoadMetrics


def test_sliding_window_counter_basic():
    counter = SlidingWindowCounter(60)
    assert counter.get_count() == 0
    counter.increment()
    assert counter.get_count() == 1
    counter.increment(3)
    assert counter.get_count() == 4


def test_sliding_window_counter_expiry():
    counter = SlidingWindowCounter(1)
    counter.increment()
    assert counter.get_count() == 1
    time.sleep(1.1)
    assert counter.get_count() == 0


def test_sliding_window_counter_with_timestamp():
    counter = SlidingWindowCounter(60)
    now = time.time()
    counter.increment(timestamp=now - 70)
    counter.increment(timestamp=now)
    assert counter.get_count() == 1


def test_resource_monitor_record_request():
    monitor = ResourceMonitor()
    request = Request(
        scene_id="scene_1",
        prompt="Hello",
        max_output_token=100
    )
    monitor.record_request(request)
    total_load = monitor.get_total_load()
    assert total_load.qpm == 1
    assert total_load.tpm > 0


def test_resource_monitor_get_total_load():
    monitor = ResourceMonitor()
    for i in range(5):
        request = Request(
            scene_id="scene_1",
            prompt=f"Request {i}",
            max_output_token=100
        )
        monitor.record_request(request)
    total_load = monitor.get_total_load()
    assert total_load.qpm == 5


def test_resource_monitor_get_scene_load():
    monitor = ResourceMonitor()
    scene1_request = Request(
        scene_id="scene_1",
        prompt="Scene 1 request",
        max_output_token=100
    )
    scene2_request = Request(
        scene_id="scene_2",
        prompt="Scene 2 request",
        max_output_token=200
    )
    monitor.record_request(scene1_request)
    monitor.record_request(scene2_request)
    monitor.record_request(scene2_request)
    scene1_load = monitor.get_scene_load("scene_1")
    scene2_load = monitor.get_scene_load("scene_2")
    assert scene1_load.qpm == 1
    assert scene2_load.qpm == 2


def test_resource_monitor_get_all_scenes_load():
    monitor = ResourceMonitor()
    request1 = Request(scene_id="scene_1", prompt="Hello", max_output_token=100)
    request2 = Request(scene_id="scene_2", prompt="Hi", max_output_token=100)
    monitor.record_request(request1)
    monitor.record_request(request2)
    all_loads = monitor.get_all_scenes_load()
    assert len(all_loads) == 2
    assert "scene_1" in all_loads
    assert "scene_2" in all_loads

