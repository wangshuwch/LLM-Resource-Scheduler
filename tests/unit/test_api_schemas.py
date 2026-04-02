import pytest
from datetime import datetime
from pydantic import ValidationError
from src.api.schemas import (
    SubmitRequest,
    SubmitResponse,
    RequestStatusResponse,
    RequestResultResponse,
    SceneConfigRequest,
    SceneConfigResponse,
    SceneConfigListResponse,
    SuccessResponse,
    SystemStatusResponse,
    QueueRequestItem,
    QueueStatusResponse,
)


class TestSubmitRequest:
    def test_create_submit_request(self):
        req = SubmitRequest(
            scene_id="test_scene",
            prompt="Test prompt",
            max_output_token=100
        )
        assert req.scene_id == "test_scene"
        assert req.prompt == "Test prompt"
        assert req.max_output_token == 100

    def test_submit_request_required_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            SubmitRequest()
        
        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "scene_id" in error_fields
        assert "prompt" in error_fields
        assert "max_output_token" in error_fields

    def test_submit_request_invalid_types(self):
        with pytest.raises(ValidationError):
            SubmitRequest(
                scene_id="test_scene",
                prompt="Test prompt",
                max_output_token="not_an_int"
            )


class TestSubmitResponse:
    def test_create_submit_response(self):
        resp = SubmitResponse(
            request_id="req_123",
            status="pending",
            queue_position=5
        )
        assert resp.request_id == "req_123"
        assert resp.status == "pending"
        assert resp.queue_position == 5

    def test_submit_response_required_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            SubmitResponse()
        
        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "request_id" in error_fields
        assert "status" in error_fields
        assert "queue_position" in error_fields


class TestRequestStatusResponse:
    def test_create_request_status_response_minimal(self):
        resp = RequestStatusResponse(
            request_id="req_123",
            scene_id="test_scene",
            status="pending"
        )
        assert resp.request_id == "req_123"
        assert resp.scene_id == "test_scene"
        assert resp.status == "pending"
        assert resp.queue_position is None
        assert resp.enqueue_time is None
        assert resp.start_time is None
        assert resp.end_time is None
        assert resp.token_consumption is None

    def test_create_request_status_response_full(self):
        now = datetime.now()
        resp = RequestStatusResponse(
            request_id="req_123",
            scene_id="test_scene",
            status="completed",
            queue_position=0,
            enqueue_time=now,
            start_time=now,
            end_time=now,
            token_consumption=150
        )
        assert resp.request_id == "req_123"
        assert resp.scene_id == "test_scene"
        assert resp.status == "completed"
        assert resp.queue_position == 0
        assert resp.enqueue_time == now
        assert resp.start_time == now
        assert resp.end_time == now
        assert resp.token_consumption == 150

    def test_request_status_response_required_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            RequestStatusResponse()
        
        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "request_id" in error_fields
        assert "scene_id" in error_fields
        assert "status" in error_fields


class TestRequestResultResponse:
    def test_create_request_result_response_minimal(self):
        resp = RequestResultResponse(
            request_id="req_123",
            scene_id="test_scene",
            status="completed"
        )
        assert resp.request_id == "req_123"
        assert resp.scene_id == "test_scene"
        assert resp.status == "completed"
        assert resp.token_consumption is None
        assert resp.result is None
        assert resp.error is None

    def test_create_request_result_response_with_result(self):
        resp = RequestResultResponse(
            request_id="req_123",
            scene_id="test_scene",
            status="completed",
            token_consumption=150,
            result={"output": "Test result"}
        )
        assert resp.token_consumption == 150
        assert resp.result == {"output": "Test result"}
        assert resp.error is None

    def test_create_request_result_response_with_error(self):
        resp = RequestResultResponse(
            request_id="req_123",
            scene_id="test_scene",
            status="failed",
            error="Processing failed"
        )
        assert resp.result is None
        assert resp.error == "Processing failed"


class TestSceneConfigRequest:
    def test_create_scene_config_request(self):
        req = SceneConfigRequest(
            scene_id="test_scene",
            priority=5,
            max_qpm=100,
            max_tpm=10000
        )
        assert req.scene_id == "test_scene"
        assert req.priority == 5
        assert req.max_qpm == 100
        assert req.max_tpm == 10000

    def test_scene_config_request_priority_validation_min(self):
        with pytest.raises(ValidationError) as exc_info:
            SceneConfigRequest(
                scene_id="test_scene",
                priority=0,
                max_qpm=100,
                max_tpm=10000
            )
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_scene_config_request_priority_validation_max(self):
        with pytest.raises(ValidationError) as exc_info:
            SceneConfigRequest(
                scene_id="test_scene",
                priority=11,
                max_qpm=100,
                max_tpm=10000
            )
        assert "less than or equal to 10" in str(exc_info.value)

    def test_scene_config_request_priority_boundary_values(self):
        req_min = SceneConfigRequest(
            scene_id="test_scene",
            priority=1,
            max_qpm=100,
            max_tpm=10000
        )
        assert req_min.priority == 1

        req_max = SceneConfigRequest(
            scene_id="test_scene",
            priority=10,
            max_qpm=100,
            max_tpm=10000
        )
        assert req_max.priority == 10

    def test_scene_config_request_required_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            SceneConfigRequest()
        
        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "scene_id" in error_fields
        assert "priority" in error_fields
        assert "max_qpm" in error_fields
        assert "max_tpm" in error_fields


class TestSceneConfigResponse:
    def test_create_scene_config_response_minimal(self):
        resp = SceneConfigResponse(
            scene_id="test_scene",
            priority=5,
            max_qpm=100,
            max_tpm=10000
        )
        assert resp.scene_id == "test_scene"
        assert resp.priority == 5
        assert resp.max_qpm == 100
        assert resp.max_tpm == 10000
        assert resp.current_qpm is None
        assert resp.current_tpm is None

    def test_create_scene_config_response_full(self):
        resp = SceneConfigResponse(
            scene_id="test_scene",
            priority=5,
            max_qpm=100,
            max_tpm=10000,
            current_qpm=50,
            current_tpm=5000
        )
        assert resp.current_qpm == 50
        assert resp.current_tpm == 5000


class TestSceneConfigListResponse:
    def test_create_scene_config_list_response_empty(self):
        resp = SceneConfigListResponse(scenes=[])
        assert resp.scenes == []

    def test_create_scene_config_list_response_with_scenes(self):
        scene1 = SceneConfigResponse(
            scene_id="scene1",
            priority=5,
            max_qpm=100,
            max_tpm=10000
        )
        scene2 = SceneConfigResponse(
            scene_id="scene2",
            priority=7,
            max_qpm=200,
            max_tpm=20000
        )
        
        resp = SceneConfigListResponse(scenes=[scene1, scene2])
        assert len(resp.scenes) == 2
        assert resp.scenes[0].scene_id == "scene1"
        assert resp.scenes[1].scene_id == "scene2"


class TestSuccessResponse:
    def test_create_success_response(self):
        scene = SceneConfigResponse(
            scene_id="test_scene",
            priority=5,
            max_qpm=100,
            max_tpm=10000
        )
        resp = SuccessResponse(success=True, scene=scene)
        assert resp.success is True
        assert resp.scene.scene_id == "test_scene"

    def test_success_response_required_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            SuccessResponse()
        
        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "success" in error_fields
        assert "scene" in error_fields


class TestSystemStatusResponse:
    def test_create_system_status_response(self):
        resp = SystemStatusResponse(
            total_qpm_limit=1000,
            total_tpm_limit=100000,
            current_total_qpm=500,
            current_total_tpm=50000,
            queue_length=10,
            processing_count=5,
            scenes={"scene1": {"qpm": 100, "tpm": 10000}}
        )
        assert resp.total_qpm_limit == 1000
        assert resp.total_tpm_limit == 100000
        assert resp.current_total_qpm == 500
        assert resp.current_total_tpm == 50000
        assert resp.queue_length == 10
        assert resp.processing_count == 5
        assert resp.scenes == {"scene1": {"qpm": 100, "tpm": 10000}}

    def test_system_status_response_required_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            SystemStatusResponse()
        
        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "total_qpm_limit" in error_fields
        assert "total_tpm_limit" in error_fields
        assert "current_total_qpm" in error_fields
        assert "current_total_tpm" in error_fields
        assert "queue_length" in error_fields
        assert "processing_count" in error_fields
        assert "scenes" in error_fields


class TestQueueRequestItem:
    def test_create_queue_request_item(self):
        now = datetime.now()
        item = QueueRequestItem(
            request_id="req_123",
            scene_id="test_scene",
            priority=5,
            enqueue_time=now,
            estimated_token_consumption=100
        )
        assert item.request_id == "req_123"
        assert item.scene_id == "test_scene"
        assert item.priority == 5
        assert item.enqueue_time == now
        assert item.estimated_token_consumption == 100

    def test_queue_request_item_required_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            QueueRequestItem()
        
        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "request_id" in error_fields
        assert "scene_id" in error_fields
        assert "priority" in error_fields
        assert "enqueue_time" in error_fields
        assert "estimated_token_consumption" in error_fields


class TestQueueStatusResponse:
    def test_create_queue_status_response_empty(self):
        resp = QueueStatusResponse(length=0, requests=[])
        assert resp.length == 0
        assert resp.requests == []

    def test_create_queue_status_response_with_requests(self):
        now = datetime.now()
        item1 = QueueRequestItem(
            request_id="req_1",
            scene_id="scene1",
            priority=5,
            enqueue_time=now,
            estimated_token_consumption=100
        )
        item2 = QueueRequestItem(
            request_id="req_2",
            scene_id="scene2",
            priority=7,
            enqueue_time=now,
            estimated_token_consumption=150
        )
        
        resp = QueueStatusResponse(length=2, requests=[item1, item2])
        assert resp.length == 2
        assert len(resp.requests) == 2
        assert resp.requests[0].request_id == "req_1"
        assert resp.requests[1].request_id == "req_2"

    def test_queue_status_response_required_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            QueueStatusResponse()
        
        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "length" in error_fields
        assert "requests" in error_fields
