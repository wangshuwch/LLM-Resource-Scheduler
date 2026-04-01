from pydantic import BaseModel


class SubmitRequest(BaseModel):
    scene_id: str
    prompt: str
    max_output_token: int


class SubmitResponse(BaseModel):
    request_id: str
    status: str
    queue_position: int
