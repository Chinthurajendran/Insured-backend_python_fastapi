from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_session
from uuid import UUID
from typing import List, Dict
from fastapi import APIRouter, Query, Depends, status, HTTPException
from .service import ChatService
from .schemas import *


messages_router = APIRouter()
chat_service = ChatService()


@messages_router.get("/messages/{receiver_id}", response_model=List[MessageSchema])
async def get_chat_history(
    receiver_id: UUID,
    sender_id: UUID = Query(...),
    session: AsyncSession = Depends(get_session)
):
    print("11111111111111111111111111111111111111")
    print("Fetching chat history for:", receiver_id, sender_id)
    message = await chat_service.get_messages(receiver_id, sender_id, session)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Messages not found")
    return message
