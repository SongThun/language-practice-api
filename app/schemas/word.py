import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WordCreate(BaseModel):
    word: str = Field(..., min_length=1, max_length=500)
    definition: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1, max_length=50)
    context_sentence: str | None = None
    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class WordUpdate(BaseModel):
    word: str | None = Field(None, min_length=1, max_length=500)
    definition: str | None = Field(None, min_length=1)
    language: str | None = Field(None, min_length=1, max_length=50)
    context_sentence: str | None = None
    tag_ids: list[uuid.UUID] | None = None


class WordStatsResponse(BaseModel):
    box: int
    last_practiced: datetime | None
    success_count: int
    fail_count: int

    model_config = {"from_attributes": True}


class TagBrief(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class WordResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    word: str
    definition: str
    language: str
    context_sentence: str | None
    created_at: datetime
    updated_at: datetime
    tags: list[TagBrief] = Field(default_factory=list)
    stats: WordStatsResponse | None = None

    model_config = {"from_attributes": True}


class WordListResponse(BaseModel):
    items: list[WordResponse]
    total: int
