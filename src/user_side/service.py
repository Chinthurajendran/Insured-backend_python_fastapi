from .models import usertable
from .schemas import*
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from datetime import datetime
from src.utils import generate_passwd_hash,UPLOAD_DIR
from fastapi import UploadFile,File
import logging
import aiofiles
from uuid import UUID
import traceback

logger = logging.getLogger(__name__)

class UserService:
    async def get_user_by_id(self,user_id:str,session:AsyncSession):
        statement = select(usertable).where(usertable.user_id == user_id)
        result = await session.exec(statement)

        user = result.first()
        
        return user

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
    
    async def exist_user_id(self,user_id:str,session:AsyncSession):
        user = await self.get_user_by_id(user_id,session)

        return True if user is not None else False
    
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

    async def profile_update(self, user_data: ProfileCreateRequest, user_Id, image: UploadFile, session: AsyncSession):
        try:
            print("zzzzzzzzzzzzzzz",image)
            file_path = UPLOAD_DIR / image.filename
            async with aiofiles.open(file_path, "wb") as buffer:
                content = await image.read()
                await buffer.write(content)

            file_url = f"http://127.0.0.1:8000/uploads/{image.filename}"

            result = await session.execute(select(usertable).where(usertable.user_id == user_Id))
            user = result.scalars().first()

            if not user:
                return {"error": "User not found"}

            user.username = user_data.username
            user.email = user_data.email
            user.phone = user_data.phone
            user.gender = user_data.gender
            user.date_of_birth = user_data.date_of_birth
            user.city = user_data.city
            user.marital_status = user_data.marital_status
            user.annual_income = user_data.annual_income
            user.image = file_url 
            user.profile_status = True 

            session.add(user)
            await session.flush()  # Ensure changes are detected
            await session.commit()  # Save changes to the database

            return {"message": "Profile updated successfully"}

        except Exception as e:
                await session.rollback()  # Rollback changes if an error occurs
                traceback.print_exc()  # Print the full error details
                return {"error": str(e)}

