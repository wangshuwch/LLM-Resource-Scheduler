
import pytest
from datetime import datetime
from src.scheduler.models import (
    RequestStatus,
    Scene,
    Request,
    LoadMetrics,
    calculate_token_consumption,
)


def test_request_status_enum():
    assert RequestStatus.PENDING.value == "pending"
    assert RequestStatus.PROCESSING.value == "processing"
    assert RequestStatus.COMPLETED.value == "completed"
    assert RequestStatus.FAILED.value == "failed"


def test_scene_creation():
    scene = Scene(
        scene_id="scene_1",
        priority=5,
        max_qpm=100,
        max_tpm=10000
    )
    assert scene.scene_id == "scene_1"
    assert scene.priority == 5
    assert scene.max_qpm == 100
    assert scene.max_tpm == 10000


def test_scene_priority_validation():
    with pytest.raises(Exception):
        Scene(
            scene_id="scene_2",
            priority=0,
            max_qpm=100,
            max_tpm=10000
        )
    
    with pytest.raises(Exception):
        Scene(
            scene_id="scene_2",
            priority=11,
            max_qpm=100,
            max_tpm=10000
        )


def test_request_creation():
    request = Request(
        scene_id="scene_1",
        prompt="Hello, world!",
        max_output_token=100
    )
    assert request.scene_id == "scene_1"
    assert request.prompt == "Hello, world!"
    assert request.max_output_token == 100
    assert isinstance(request.request_id, str)
    assert len(request.request_id) > 0
    assert isinstance(request.created_at, datetime)


def test_request_with_custom_id():
    custom_id = "custom_request_123"
    request = Request(
        request_id=custom_id,
        scene_id="scene_1",
        prompt="Hello",
        max_output_token=50
    )
    assert request.request_id == custom_id


def test_load_metrics():
    metrics = LoadMetrics(qpm=50, tpm=5000)
    assert metrics.qpm == 50
    assert metrics.tpm == 5000


def test_calculate_token_consumption():
    request = Request(
        scene_id="scene_1",
        prompt="Hello, how are you?",
        max_output_token=200
    )
    token_count = calculate_token_consumption(request)
    assert isinstance(token_count, int)
    assert token_count > 0
