from .models import usertable
from .schemas import*
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from datetime import datetime
from src.utils import generate_passwd_hash,UPLOAD_DIR,random_code
from fastapi import UploadFile,File,HTTPException,status
import logging
import aiofiles
from uuid import UUID
import traceback
from dotenv import load_dotenv
import os
import boto3
from src.admin_side.models import*

load_dotenv()

logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION')

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

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
            if image is not None:
                    folder_name = "Users/"

                    file_path = f"{folder_name}{image.filename}"

                    s3_client.upload_fileobj(image.file, BUCKET_NAME, file_path)
                    file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_path}"

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
            if image is not None:
                user.image = file_url 
            user.profile_status = True 

            session.add(user)
            await session.flush() 
            await session.commit() 

            return {"message": "Profile updated successfully"}

        except Exception as e:
                await session.rollback() 
                traceback.print_exc()
                return {"error": str(e)}


    async def PolicyCreation(self, user_data: PolicyRegistration, 
                                policyId, 
                                userId,
                                id_proof: UploadFile,
                                passbook: UploadFile,
                                income_proof: UploadFile,
                                photo: UploadFile,
                                pan_card: UploadFile,
                                nominee_address_proof: UploadFile,
                                session: AsyncSession):
        try:
            async def upload_to_s3(file: UploadFile, folder_name: str) -> str:
                file_path = f"{folder_name}/{file.filename}"
                s3_client.upload_fileobj(file.file, BUCKET_NAME, file_path)
                file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_path}"
                return file_url

            code = random_code()
            
            folder_name = f"User/PolicyDocuments/EUPC{code}"

            id_proof_url = await upload_to_s3(id_proof, folder_name) if id_proof else None
            passbook_url = await upload_to_s3(passbook, folder_name) if passbook else None
            income_proof_url = await upload_to_s3(income_proof, folder_name) if income_proof else None
            photo_url = await upload_to_s3(photo, folder_name) if photo else None
            pan_card_url = await upload_to_s3(pan_card, folder_name) if pan_card else None
            nominee_address_proof_url = await upload_to_s3(nominee_address_proof, folder_name) if nominee_address_proof else None

            policy_result = await session.execute(select(policytable).where(policytable.policy_uid == policyId))
            policys = policy_result.scalars().first()

            users_result = await session.execute(select(usertable).where(usertable.user_id == userId))
            users = users_result.scalars().first()
            create_at = datetime.utcnow()
            update_at = datetime.utcnow()
            date_of_payment = datetime.utcnow()
            coverage = policys.coverage
            print("ppppppppppppppp",coverage)
            settlement = policys.settlement
            premium_amount = float(policys.premium_amount)  

            dob = users.date_of_birth
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

            r = 0.06  
            n = 12  
            t = int(coverage) - age 

            if t > 0: 
                monthly_payment = (premium_amount * (r / n)) / (1 - pow(1 + (r / n), -n * t))
            else:
                monthly_payment = premium_amount / 12  

            new_policy = PolicyDetails(
                user_id=users.user_id,
                policy_id=policys.policy_uid,
                policy_holder=users.username,
                email = users.email,
                gender = users.gender,
                phone = users.phone,
                marital_status = users.marital_status,
                city = users.city,
                policy_name=policys.policy_name,
                policy_type=policys.policy_type,
                nominee_name=user_data.nominee_name,
                nominee_relationship=user_data.nominee_relationship,
                coverage=policys.coverage,
                settlement=policys.settlement,
                premium_amount=policys.premium_amount,
                income_range=policys.income_range,
                monthly_amount=monthly_payment,
                age=str(age),
                date_of_birth = users.date_of_birth,
                id_proof=id_proof_url,
                passbook=passbook_url,
                photo=photo_url,
                pan_card=pan_card_url,
                income_proof=income_proof_url,
                nominee_address_proof=nominee_address_proof_url,
                date_of_payment=date_of_payment,
                create_at=create_at,
                update_at=update_at
            )

            session.add(new_policy)
            await session.flush() 
            await session.commit()

            return {"message": "Profile updated successfully"}

        except Exception as e:
            await session.rollback()
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": f"An error occurred: {str(e)}"}
            )
