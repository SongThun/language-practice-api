import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WordSelectionRequest(BaseModel):
    language: str = Field(..., min_length=1, max_length=50)
    count: int = Field(default=5, ge=1, le=20)
    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class SelectedWord(BaseModel):
    id: uuid.UUID
    word: str
    definition: str
    language: str
    example_sentence: str | None = None

    model_config = {"from_attributes": True}


class PracticeSessionCreate(BaseModel):
    language: str = Field(..., min_length=1, max_length=50)
    word_ids: list[uuid.UUID] = Field(..., min_length=1)


class PracticeSessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    language: str
    word_count: int
    status: str = "active"
    user_writing: str | None
    feedback: str | None
    created_at: datetime
    completed_at: datetime | None
    results: list["PracticeResultResponse"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PracticeResultResponse(BaseModel):
    id: uuid.UUID
    word_id: uuid.UUID
    is_correct: bool | None
    feedback: str | None

    model_config = {"from_attributes": True}


class EvaluationRequest(BaseModel):
    user_writing: str = Field(..., min_length=1, max_length=5000)


class WordEvaluation(BaseModel):
    word_id: uuid.UUID
    word: str
    is_correct: bool
    feedback: str


class EvaluationResponse(BaseModel):
    session_id: uuid.UUID
    overall_feedback: str
    grammar_notes: str
    word_evaluations: list[WordEvaluation]


class ExampleGenerationRequest(BaseModel):
    word_ids: list[uuid.UUID] = Field(..., min_length=1)
