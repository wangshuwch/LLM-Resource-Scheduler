from pydantic import BaseModel, Field
from datetime import datetime


class SubmitRequest(BaseModel):
    scene_id: str
    prompt: str
    max_output_token: int


class SubmitResponse(BaseModel):
    request_id: str
    status: str
    queue_position: int


class RequestStatusResponse(BaseModel):
    request_id: str
    scene_id: str
    status: str
    queue_position: int | None = None
    enqueue_time: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    token_consumption: int | None = None


class RequestResultResponse(BaseModel):
    request_id: str
    scene_id: str
    status: str
    token_consumption: int | None = None
    result: dict | None = None
    error: str | None = None


class SceneConfigRequest(BaseModel):
    scene_id: str
    priority: int = Field(ge=1, le=10)
    max_qpm: int
    max_tpm: int


class SceneConfigResponse(BaseModel):
    scene_id: str
    priority: int
    max_qpm: int
    max_tpm: int
    current_qpm: int | None = None
    current_tpm: int | None = None


class SceneConfigListResponse(BaseModel):
    scenes: list[SceneConfigResponse]


class SuccessResponse(BaseModel):
    success: bool
    scene: SceneConfigResponse


class SystemStatusResponse(BaseModel):
    total_qpm_limit: int
    total_tpm_limit: int
    current_total_qpm: int
    current_total_tpm: int
    queue_length: int
    processing_count: int
    scenes: dict


class QueueRequestItem(BaseModel):
    request_id: str
    scene_id: str
    priority: int
    enqueue_time: datetime
    estimated_token_consumption: int


class QueueStatusResponse(BaseModel):
    length: int
    requests: list[QueueRequestItem]
