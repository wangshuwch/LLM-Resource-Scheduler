import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from src.main import app
from src.scheduler.models import Request, Scene, RequestStatus


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_scheduler():
    with patch('src.main.scheduler') as mock:
        yield mock


@pytest.fixture
def mock_resource_monitor():
    with patch('src.main.resource_monitor') as mock:
        yield mock


class TestRootEndpoint:
    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "app_name" in data
        assert "status" in data
        assert data["status"] == "healthy"


class TestSubmitRequest:
    def test_submit_request_success(self, client, mock_scheduler):
        mock_request = MagicMock()
        mock_request.scene_id = "test_scene"
        mock_request.prompt = "Test prompt"
        mock_request.max_output_token = 100
        
        mock_scheduler.submit_request = AsyncMock(return_value="req_123")
        mock_scheduler.get_request_status = MagicMock(return_value=MagicMock(value="pending"))
        mock_scheduler.request_queue = []
        
        response = client.post(
            "/api/v1/requests",
            json={
                "scene_id": "test_scene",
                "prompt": "Test prompt",
                "max_output_token": 100
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "request_id" in data
        assert "status" in data
        assert "queue_position" in data

    def test_submit_request_invalid_scene(self, client, mock_scheduler):
        mock_scheduler.submit_request = AsyncMock(side_effect=ValueError("Scene not registered"))
        
        response = client.post(
            "/api/v1/requests",
            json={
                "scene_id": "invalid_scene",
                "prompt": "Test prompt",
                "max_output_token": 100
            }
        )
        
        assert response.status_code == 400
        assert "Scene not registered" in response.json()["detail"]

    def test_submit_request_missing_fields(self, client):
        response = client.post(
            "/api/v1/requests",
            json={}
        )
        
        assert response.status_code == 422

    def test_submit_request_invalid_token_type(self, client):
        response = client.post(
            "/api/v1/requests",
            json={
                "scene_id": "test_scene",
                "prompt": "Test prompt",
                "max_output_token": "not_an_int"
            }
        )
        
        assert response.status_code == 422

    def test_submit_request_internal_error(self, client, mock_scheduler):
        mock_scheduler.submit_request = AsyncMock(side_effect=Exception("Internal error"))
        
        response = client.post(
            "/api/v1/requests",
            json={
                "scene_id": "test_scene",
                "prompt": "Test prompt",
                "max_output_token": 100
            }
        )
        
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"


class TestGetRequestStatus:
    def test_get_request_status_success(self, client, mock_scheduler):
        mock_request = MagicMock()
        mock_request.scene_id = "test_scene"
        mock_request.enqueue_time = datetime.now()
        mock_request.start_time = datetime.now()
        mock_request.end_time = None
        mock_request.token_consumption = 150
        
        mock_scheduler.get_request_status = MagicMock(return_value=MagicMock(value="processing"))
        mock_scheduler.processing_requests = {"req_123": mock_request}
        mock_scheduler.completed_requests = {}
        mock_scheduler.request_queue = []
        
        response = client.get("/api/v1/requests/req_123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "req_123"
        assert data["scene_id"] == "test_scene"
        assert data["status"] == "processing"

    def test_get_request_status_not_found(self, client, mock_scheduler):
        mock_scheduler.get_request_status = MagicMock(return_value=None)
        
        response = client.get("/api/v1/requests/nonexistent")
        
        assert response.status_code == 404
        assert "Request not found" in response.json()["detail"]

    def test_get_request_status_in_queue(self, client, mock_scheduler):
        mock_request = MagicMock()
        mock_request.scene_id = "test_scene"
        mock_request.enqueue_time = datetime.now()
        mock_request.start_time = None
        mock_request.end_time = None
        mock_request.token_consumption = None
        
        mock_scheduler.get_request_status = MagicMock(return_value=MagicMock(value="pending"))
        mock_scheduler.processing_requests = {}
        mock_scheduler.completed_requests = {}
        mock_scheduler.request_queue = [(-5, datetime.now().timestamp(), "req_123", mock_request)]
        
        response = client.get("/api/v1/requests/req_123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

    def test_get_request_status_internal_error(self, client, mock_scheduler):
        mock_scheduler.get_request_status = MagicMock(side_effect=Exception("Internal error"))
        
        response = client.get("/api/v1/requests/req_123")
        
        assert response.status_code == 500


class TestGetRequestResult:
    def test_get_request_result_success(self, client, mock_scheduler):
        mock_request = MagicMock()
        mock_request.scene_id = "test_scene"
        mock_request.token_consumption = 150
        
        mock_scheduler.get_request_status = MagicMock(return_value=MagicMock(value="completed"))
        mock_scheduler.processing_requests = {}
        mock_scheduler.completed_requests = {"req_123": mock_request}
        mock_scheduler.request_queue = []
        mock_scheduler.get_request_result = MagicMock(return_value={
            "result": {"output": "Test result"},
            "error": None
        })
        
        response = client.get("/api/v1/requests/req_123/result")
        
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "req_123"
        assert data["status"] == "completed"
        assert data["result"] == {"output": "Test result"}

    def test_get_request_result_with_error(self, client, mock_scheduler):
        mock_request = MagicMock()
        mock_request.scene_id = "test_scene"
        mock_request.token_consumption = 0
        
        mock_scheduler.get_request_status = MagicMock(return_value=MagicMock(value="failed"))
        mock_scheduler.processing_requests = {}
        mock_scheduler.completed_requests = {"req_123": mock_request}
        mock_scheduler.request_queue = []
        mock_scheduler.get_request_result = MagicMock(return_value={
            "result": None,
            "error": "Processing failed"
        })
        
        response = client.get("/api/v1/requests/req_123/result")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Processing failed"

    def test_get_request_result_not_found(self, client, mock_scheduler):
        mock_scheduler.get_request_status = MagicMock(return_value=None)
        
        response = client.get("/api/v1/requests/nonexistent/result")
        
        assert response.status_code == 404

    def test_get_request_result_internal_error(self, client, mock_scheduler):
        mock_scheduler.get_request_status = MagicMock(side_effect=Exception("Internal error"))
        
        response = client.get("/api/v1/requests/req_123/result")
        
        assert response.status_code == 500


class TestCreateOrUpdateScene:
    def test_create_scene_success(self, client, mock_scheduler, mock_resource_monitor):
        mock_scene = Scene(
            scene_id="new_scene",
            priority=5,
            max_qpm=100,
            max_tpm=10000
        )
        
        mock_scheduler.scene_config_manager.add_or_update_scene = MagicMock(return_value=True)
        mock_scheduler.register_scene = MagicMock()
        mock_resource_monitor.get_scene_load = MagicMock(return_value=MagicMock(qpm=0, tpm=0))
        
        response = client.put(
            "/api/v1/scenes/new_scene",
            json={
                "scene_id": "new_scene",
                "priority": 5,
                "max_qpm": 100,
                "max_tpm": 10000
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["scene"]["scene_id"] == "new_scene"

    def test_update_scene_success(self, client, mock_scheduler, mock_resource_monitor):
        mock_scheduler.scene_config_manager.add_or_update_scene = MagicMock(return_value=True)
        mock_scheduler.register_scene = MagicMock()
        mock_resource_monitor.get_scene_load = MagicMock(return_value=MagicMock(qpm=50, tpm=5000))
        
        response = client.put(
            "/api/v1/scenes/existing_scene",
            json={
                "scene_id": "existing_scene",
                "priority": 7,
                "max_qpm": 200,
                "max_tpm": 20000
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_create_scene_id_mismatch(self, client):
        response = client.put(
            "/api/v1/scenes/scene_a",
            json={
                "scene_id": "scene_b",
                "priority": 5,
                "max_qpm": 100,
                "max_tpm": 10000
            }
        )
        
        assert response.status_code == 400
        assert "must match" in response.json()["detail"]

    def test_create_scene_invalid_priority(self, client):
        response = client.put(
            "/api/v1/scenes/test_scene",
            json={
                "scene_id": "test_scene",
                "priority": 15,
                "max_qpm": 100,
                "max_tpm": 10000
            }
        )
        
        assert response.status_code == 422

    def test_create_scene_missing_fields(self, client):
        response = client.put(
            "/api/v1/scenes/test_scene",
            json={}
        )
        
        assert response.status_code == 422

    def test_create_scene_internal_error(self, client, mock_scheduler):
        mock_scheduler.scene_config_manager.add_or_update_scene = MagicMock(side_effect=Exception("Internal error"))
        
        response = client.put(
            "/api/v1/scenes/test_scene",
            json={
                "scene_id": "test_scene",
                "priority": 5,
                "max_qpm": 100,
                "max_tpm": 10000
            }
        )
        
        assert response.status_code == 500


class TestGetSceneConfig:
    def test_get_scene_config_success(self, client, mock_scheduler, mock_resource_monitor):
        mock_scene = Scene(
            scene_id="test_scene",
            priority=5,
            max_qpm=100,
            max_tpm=10000
        )
        
        mock_scheduler.scene_config_manager.get_scene = MagicMock(return_value=mock_scene)
        mock_resource_monitor.get_scene_load = MagicMock(return_value=MagicMock(qpm=50, tpm=5000))
        
        response = client.get("/api/v1/scenes/test_scene")
        
        assert response.status_code == 200
        data = response.json()
        assert data["scene_id"] == "test_scene"
        assert data["priority"] == 5
        assert data["current_qpm"] == 50
        assert data["current_tpm"] == 5000

    def test_get_scene_config_not_found(self, client, mock_scheduler):
        mock_scheduler.scene_config_manager.get_scene = MagicMock(return_value=None)
        
        response = client.get("/api/v1/scenes/nonexistent")
        
        assert response.status_code == 404
        assert "Scene not found" in response.json()["detail"]

    def test_get_scene_config_internal_error(self, client, mock_scheduler):
        mock_scheduler.scene_config_manager.get_scene = MagicMock(side_effect=Exception("Internal error"))
        
        response = client.get("/api/v1/scenes/test_scene")
        
        assert response.status_code == 500


class TestGetAllSceneConfigs:
    def test_get_all_scene_configs_success(self, client, mock_scheduler, mock_resource_monitor):
        scene1 = Scene(scene_id="scene1", priority=5, max_qpm=100, max_tpm=10000)
        scene2 = Scene(scene_id="scene2", priority=7, max_qpm=200, max_tpm=20000)
        
        mock_scheduler.scene_config_manager.get_all_scenes = MagicMock(return_value={
            "scene1": scene1,
            "scene2": scene2
        })
        mock_resource_monitor.get_scene_load = MagicMock(return_value=MagicMock(qpm=50, tpm=5000))
        
        response = client.get("/api/v1/scenes")
        
        assert response.status_code == 200
        data = response.json()
        assert "scenes" in data
        assert len(data["scenes"]) == 2

    def test_get_all_scene_configs_empty(self, client, mock_scheduler, mock_resource_monitor):
        mock_scheduler.scene_config_manager.get_all_scenes = MagicMock(return_value={})
        mock_resource_monitor.get_scene_load = MagicMock(return_value=MagicMock(qpm=0, tpm=0))
        
        response = client.get("/api/v1/scenes")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["scenes"]) == 0

    def test_get_all_scene_configs_internal_error(self, client, mock_scheduler):
        mock_scheduler.scene_config_manager.get_all_scenes = MagicMock(side_effect=Exception("Internal error"))
        
        response = client.get("/api/v1/scenes")
        
        assert response.status_code == 500


class TestGetSystemStatus:
    def test_get_system_status_success(self, client, mock_scheduler):
        mock_scheduler.get_system_status = MagicMock(return_value={
            "total_qpm_limit": 1000,
            "total_tpm_limit": 100000,
            "current_total_qpm": 500,
            "current_total_tpm": 50000,
            "queue_length": 10,
            "processing_count": 5,
            "scenes": {}
        })
        
        response = client.get("/api/v1/system/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_qpm_limit"] == 1000
        assert data["total_tpm_limit"] == 100000
        assert data["current_total_qpm"] == 500
        assert data["queue_length"] == 10

    def test_get_system_status_internal_error(self, client, mock_scheduler):
        mock_scheduler.get_system_status = MagicMock(side_effect=Exception("Internal error"))
        
        response = client.get("/api/v1/system/status")
        
        assert response.status_code == 500


class TestGetQueueStatus:
    def test_get_queue_status_success(self, client, mock_scheduler):
        mock_request = MagicMock()
        mock_request.scene_id = "test_scene"
        mock_request.token_consumption = 100
        
        mock_scheduler.request_queue = [
            (-5, datetime.now().timestamp(), "req_1", mock_request),
            (-7, datetime.now().timestamp(), "req_2", mock_request)
        ]
        
        response = client.get("/api/v1/queue")
        
        assert response.status_code == 200
        data = response.json()
        assert data["length"] == 2
        assert len(data["requests"]) == 2

    def test_get_queue_status_empty(self, client, mock_scheduler):
        mock_scheduler.request_queue = []
        
        response = client.get("/api/v1/queue")
        
        assert response.status_code == 200
        data = response.json()
        assert data["length"] == 0
        assert len(data["requests"]) == 0

    def test_get_queue_status_internal_error(self, client, mock_scheduler):
        mock_scheduler.request_queue = None
        
        response = client.get("/api/v1/queue")
        
        assert response.status_code == 500


class TestAPIIntegration:
    def test_complete_request_flow(self, client, mock_scheduler, mock_resource_monitor):
        mock_request = MagicMock()
        mock_request.scene_id = "test_scene"
        mock_request.prompt = "Test prompt"
        mock_request.max_output_token = 100
        mock_request.enqueue_time = datetime.now()
        mock_request.start_time = datetime.now()
        mock_request.end_time = None
        mock_request.token_consumption = 150
        
        mock_scheduler.submit_request = AsyncMock(return_value="req_123")
        mock_scheduler.get_request_status = MagicMock(return_value=MagicMock(value="pending"))
        mock_scheduler.request_queue = [(-5, datetime.now().timestamp(), "req_123", mock_request)]
        
        submit_response = client.post(
            "/api/v1/requests",
            json={
                "scene_id": "test_scene",
                "prompt": "Test prompt",
                "max_output_token": 100
            }
        )
        
        assert submit_response.status_code == 200
        request_id = submit_response.json()["request_id"]
        
        mock_scheduler.get_request_status = MagicMock(return_value=MagicMock(value="processing"))
        mock_scheduler.processing_requests = {request_id: mock_request}
        mock_scheduler.request_queue = []
        
        status_response = client.get(f"/api/v1/requests/{request_id}")
        
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "processing"

    def test_scene_management_flow(self, client, mock_scheduler, mock_resource_monitor):
        mock_scheduler.scene_config_manager.add_or_update_scene = MagicMock(return_value=True)
        mock_scheduler.register_scene = MagicMock()
        mock_resource_monitor.get_scene_load = MagicMock(return_value=MagicMock(qpm=0, tpm=0))
        
        create_response = client.put(
            "/api/v1/scenes/test_scene",
            json={
                "scene_id": "test_scene",
                "priority": 5,
                "max_qpm": 100,
                "max_tpm": 10000
            }
        )
        
        assert create_response.status_code == 200
        
        mock_scene = Scene(
            scene_id="test_scene",
            priority=5,
            max_qpm=100,
            max_tpm=10000
        )
        mock_scheduler.scene_config_manager.get_scene = MagicMock(return_value=mock_scene)
        mock_resource_monitor.get_scene_load = MagicMock(return_value=MagicMock(qpm=10, tpm=1000))
        
        get_response = client.get("/api/v1/scenes/test_scene")
        
        assert get_response.status_code == 200
        assert get_response.json()["scene_id"] == "test_scene"
