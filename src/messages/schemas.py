from pydantic import BaseModel
import uuid
from datetime import datetime


class MessageBase(BaseModel):
    sender_id: str
    receiver_id: str
    content: str

class MessageCreate(MessageBase):
    pass

class MessageSchema(BaseModel):
    uid: uuid.UUID
    content: str
    created_at: datetime
    sender_id: uuid.UUID
    receiver_id: uuid.UUID
