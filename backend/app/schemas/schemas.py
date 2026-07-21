import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


# ─── Auth ────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    privacy_accepted: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    status: str
    is_admin: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    deleted_at: Optional[datetime] = None
    original_email: Optional[str] = None
    # Apps liberados pro usuário ("epub"/"thumbs") — admin sempre tem todos,
    # computado à parte (não vem direto do ORM); ver app/services/user_service.py.
    app_access: list[str] = Field(default_factory=list)


class RegisterResponse(BaseModel):
    message: str
    status: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AppAccessUpdate(BaseModel):
    epub: bool = False
    thumbs: bool = False
