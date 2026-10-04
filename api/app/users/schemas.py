import uuid
from datetime import datetime

from pydantic import EmailStr

from app.config.schemas import APIModel


class UserCreate(APIModel):
    email: EmailStr


class UserUpdate(APIModel):
    email: EmailStr


class UserRead(APIModel):
    id: uuid.UUID
    email: EmailStr
    created_at: datetime
    updated_at: datetime
