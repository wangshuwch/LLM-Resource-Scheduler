"""API数据模型定义模块。

本模块定义了所有API请求和响应的Pydantic模型，
用于数据验证和序列化。

主要模型:
    - SubmitRequest/SubmitResponse: 请求提交相关
    - RequestStatusResponse/RequestResultResponse: 请求状态和结果查询
    - SceneConfigRequest/SceneConfigResponse: 场景配置相关
    - SystemStatusResponse: 系统状态
    - QueueStatusResponse: 队列状态
"""

from pydantic import BaseModel, Field
from datetime import datetime


class SubmitRequest(BaseModel):
    """请求提交模型。

    Attributes:
        scene_id: 场景ID。
        prompt: 输入提示词。
        max_output_token: 最大输出Token数。
    """

    scene_id: str
    prompt: str
    max_output_token: int


class SubmitResponse(BaseModel):
    """请求提交响应模型。

    Attributes:
        request_id: 请求ID。
        status: 请求状态。
        queue_position: 队列位置。
        estimated_wait_time_ms: 预估等待时间（毫秒）。
    """

    request_id: str
    status: str
    queue_position: int
    estimated_wait_time_ms: int | None = Field(None, description="预估等待时间（毫秒），如果请求立即处理则为None")


class RequestStatusResponse(BaseModel):
    """请求状态响应模型。

    Attributes:
        request_id: 请求ID。
        scene_id: 场景ID。
        status: 请求状态。
        queue_position: 队列位置（仅排队中的请求）。
        enqueue_time: 入队时间。
        start_time: 开始处理时间。
        end_time: 结束时间。
        token_consumption: Token消耗量。
    """

    request_id: str
    scene_id: str
    status: str
    queue_position: int | None = None
    enqueue_time: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    token_consumption: int | None = None


class RequestResultResponse(BaseModel):
    """请求结果响应模型。

    Attributes:
        request_id: 请求ID。
        scene_id: 场景ID。
        status: 请求状态。
        token_consumption: Token消耗量。
        result: 处理结果（成功时）。
        error: 错误信息（失败时）。
    """

    request_id: str
    scene_id: str
    status: str
    token_consumption: int | None = None
    result: dict | None = None
    error: str | None = None


class SceneConfigRequest(BaseModel):
    """场景配置请求模型。

    Attributes:
        scene_id: 场景ID。
        priority: 优先级（1-10）。
        max_qpm: 最大QPM限制。
        max_tpm: 最大TPM限制。
    """

    scene_id: str
    priority: int = Field(ge=1, le=10)
    max_qpm: int
    max_tpm: int


class SceneConfigResponse(BaseModel):
    """场景配置响应模型。

    Attributes:
        scene_id: 场景ID。
        priority: 优先级。
        max_qpm: 最大QPM限制。
        max_tpm: 最大TPM限制。
        current_qpm: 当前QPM。
        current_tpm: 当前TPM。
    """

    scene_id: str
    priority: int
    max_qpm: int
    max_tpm: int
    current_qpm: int | None = None
    current_tpm: int | None = None


class SceneConfigListResponse(BaseModel):
    """场景配置列表响应模型。

    Attributes:
        scenes: 场景配置列表。
    """

    scenes: list[SceneConfigResponse]


class SuccessResponse(BaseModel):
    """成功响应模型。

    Attributes:
        success: 操作是否成功。
        scene: 场景配置信息。
    """

    success: bool
    scene: SceneConfigResponse


class SystemStatusResponse(BaseModel):
    """系统状态响应模型。

    Attributes:
        total_qpm_limit: 全局QPM限制。
        total_tpm_limit: 全局TPM限制。
        current_total_qpm: 当前全局QPM。
        current_total_tpm: 当前全局TPM。
        queue_length: 队列长度。
        processing_count: 处理中请求数量。
        scenes: 各场景状态字典。
    """

    total_qpm_limit: int
    total_tpm_limit: int
    current_total_qpm: int
    current_total_tpm: int
    queue_length: int
    processing_count: int
    scenes: dict


class QueueRequestItem(BaseModel):
    """队列请求项模型。

    Attributes:
        request_id: 请求ID。
        scene_id: 场景ID。
        priority: 优先级。
        enqueue_time: 入队时间。
        estimated_token_consumption: 预估Token消耗。
    """

    request_id: str
    scene_id: str
    priority: int
    enqueue_time: datetime
    estimated_token_consumption: int


class QueueStatusResponse(BaseModel):
    """队列状态响应模型。

    Attributes:
        length: 队列长度。
        requests: 队列中的请求列表。
    """

    length: int
    requests: list[QueueRequestItem]
