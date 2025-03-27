from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid
import sqlalchemy.dialects.postgresql as pg
from typing import Optional
from datetime import datetime, timezone

class Message(SQLModel, table=True):
    uid: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID,
            nullable=False, 
            primary_key=True,
            default=uuid.uuid4  
        )
    )
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sender_id: uuid.UUID = Field(sa_column=Column(pg.UUID, nullable=False))
    receiver_id: uuid.UUID = Field(sa_column=Column(pg.UUID, nullable=False))




