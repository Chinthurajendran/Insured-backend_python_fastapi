from .models import usertable
from .schemas import UserCreate,UserModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from datetime import datetime
from src.utils import generate_passwd_hash
import logging

logger = logging.getLogger(__name__)

class UserService:
    async def get_user_by_email(self,email:str,session:AsyncSession):
        statement = select(usertable).where(usertable.email == email)
        result = await session.exec(statement)

        user = result.first()
        
        return user
    
    async def get_user_by_username(self,username:str,session:AsyncSession):
        statement = select(usertable).where(usertable.username == username)

        result = await session.exec(statement)
        user  = result.first()
        return user

    async def exist_email(self,email:str,session:AsyncSession):
        user = await self.get_user_by_email(email,session)

        return True if user is not None else False
    
    async def exist_username(self,username:str,session:AsyncSession):
        user  = await self.get_user_by_username(username,session)

        return True if user  is not None else False
    
    async def create_user(self,user_details:UserCreate,session:AsyncSession):
        user_data_dict = user_details.model_dump()
        create_at = datetime.utcnow()
        update_at = datetime.utcnow()

        new_user = usertable(
            **user_data_dict,
            create_at = create_at,
            update_at = update_at
        )
        new_user.password = generate_passwd_hash(user_data_dict['password'])
 
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        return new_user

