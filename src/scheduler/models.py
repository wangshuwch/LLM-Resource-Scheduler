
import enum
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
import tiktoken


class RequestStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Scene(BaseModel):
    scene_id: str
    priority: int = Field(ge=1, le=10)
    max_qpm: int
    max_tpm: int


class Request(BaseModel):
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    scene_id: str
    prompt: str
    max_output_token: int
    created_at: datetime = Field(default_factory=datetime.now)


class LoadMetrics(BaseModel):
    qpm: int
    tpm: int


def calculate_token_consumption(request: Request) -> int:
    encoding = tiktoken.get_encoding("cl100k_base")
    encoded_prompt = encoding.encode(request.prompt)
    return len(encoded_prompt) + request.max_output_token

