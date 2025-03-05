from .models import*
from .schemas import*
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from datetime import datetime
from src.utils import generate_passwd_hash,UPLOAD_DIR,random_code
from fastapi import UploadFile,File
import logging
import aiofiles
from uuid import UUID
import traceback
from dotenv import load_dotenv
import os
import boto3

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

class AdminService:

    async def get_policy_name(self,policy_name:str,session:AsyncSession):
        statement = select(policytable).where(policytable.policy_name == policy_name)
        result = await session.exec(statement)

        policy = result.first()
        
        return policy

    async def exist_policy(self,policy_name:str,session:AsyncSession):
        policy = await self.get_policy_name(policy_name,session)

        return True if policy is not None else False
    
    async def create_new_policy(self,policy_data:PolicyCreateRequest,session:AsyncSession):

        code = random_code()

        new_policy = policytable(
            policy_id=f"PL{code}",
            policy_name=policy_data.policy_name.lower(),
            policy_type=policy_data.policy_type,
            id_proof=policy_data.id_proof,
            passbook=policy_data.passbook,
            photo=policy_data.photo,
            pan_card=policy_data.pan_card,
            income_proof=policy_data.income_proof,
            nominee_address_proof=policy_data.nominee_address_proof,
            coverage=policy_data.coverage,
            settlement=policy_data.settlement,
            premium_amount=policy_data.premium_amount,
            age_group=policy_data.age_group,
            income_range=policy_data.income_range,
            description=policy_data.description,
            create_at=datetime.utcnow(),
            update_at=datetime.utcnow()
        )

        session.add(new_policy)
        await session.commit()
        await session.refresh(new_policy)

        return new_policy

    