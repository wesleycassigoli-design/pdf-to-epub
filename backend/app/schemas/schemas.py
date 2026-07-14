import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


# ─── Chapter ────────────────────────────────────────────────────────────────
class ChapterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    book_id: uuid.UUID
    title: str
    chapter_number: int
    start_page: Optional[int]
    end_page: Optional[int]
    epub_file: Optional[str]
    created_at: datetime


# ─── Conversion ─────────────────────────────────────────────────────────────
class ConversionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    book_id: uuid.UUID
    task_id: Optional[str]
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_ms: Optional[int]
    logs: Optional[str]
    created_at: datetime


# ─── Book ────────────────────────────────────────────────────────────────────
class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    original_name: str
    file_size_bytes: Optional[int]
    page_count: Optional[int]
    original_pdf: Optional[str]
    full_epub: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    chapters: list[ChapterOut] = []


class BookListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_name: str
    file_size_bytes: Optional[int]
    page_count: Optional[int]
    status: str
    created_at: datetime
    chapters_count: int = 0


# ─── Upload response ────────────────────────────────────────────────────────
class UploadResponse(BaseModel):
    book_id: uuid.UUID
    task_id: str
    message: str


# ─── Status response ─────────────────────────────────────────────────────────
class StatusResponse(BaseModel):
    book_id: uuid.UUID
    book_status: str
    conversion_status: Optional[str]
    task_id: Optional[str]
    progress_message: str
    chapters_count: int
    full_epub_ready: bool


# ─── Standard error ─────────────────────────────────────────────────────────
class ErrorResponse(BaseModel):
    error: dict
