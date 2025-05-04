from .schemas import *
from sqlmodel.ext.asyncio.session import AsyncSession
from .models import *
import pytz
from datetime import datetime 
from uuid import UUID
from sqlalchemy import or_
from sqlmodel import select

class ChatService:
    async def create_message(self, message: MessageCreate, user_id: str, session: AsyncSession):
        ist = pytz.timezone("Asia/Kolkata")
        utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
        local_time = utc_time.astimezone(ist).replace(tzinfo=None)

        message_instance = Message(
            sender_id=message.sender_id,
            receiver_id=message.receiver_id,
            content=message.content,
            created_at=local_time
        )
        session.add(message_instance)
        await session.commit()
        await session.refresh(message_instance)
        
        return message_instance
    
    async def get_messages(self, receiver_id: UUID, sender_id: UUID, session: AsyncSession):
        try:
            result = await session.execute(
                select(Message).where(
                    or_(
                        (Message.sender_id == sender_id) & (Message.receiver_id == receiver_id),
                        (Message.sender_id == receiver_id) & (Message.receiver_id == sender_id)
                    )
                ).order_by(Message.created_at)
            )
            return result.scalars().all()
        except Exception as e:
            print(f"Error retrieving messages: {e}")
            return [] 