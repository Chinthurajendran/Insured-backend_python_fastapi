from .models import*
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
from botocore.exceptions import ClientError
from datetime import datetime
from typing import Optional
import asyncio
from sqlalchemy import update
import mimetypes
import pytz
from src.user_side.models import*
import re

load_dotenv()

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


class Validation:
    async def validate_text(self, text: str, session: AsyncSession) -> bool:
        if not text:
            return False
        return bool(re.match(r"^[A-Za-z\s]+$", text))
    
    async def titledescription(self, text: str, session: AsyncSession) -> bool:
        if not text:
            return False
        if not re.match(r"^[A-Za-z\s.,'-]+$", text):
            return False
        if len(text.strip().split()) < 20:
            return False
        return True

    async def description(self, text: str, session: AsyncSession) -> bool:
        if not text:
            return False
        if not re.match(r"^[A-Za-z\s.,'-]+$", text):
            return False
        if len(text.strip().split()) < 50:
            return False
        return True
    
    async def validate_city(self, text: str, session: AsyncSession) -> bool:
        if not text:
            return False
        return bool(re.match(r"^[A-Za-z\s.,'-]+$", text))

    async def validate_email(self, email: str, session: AsyncSession) -> bool:
        return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w{2,4}$", email))

    async def validate_phone(self, phone: str, session: AsyncSession) -> bool:
        if not phone:
            return False
        return bool(re.match(r"^[6-9]\d{9}$", phone))

    async def validate_file_type(self, image: UploadFile, session: AsyncSession) -> bool:
        if image is None:
            return True
        return image.filename.lower().endswith((".jpg", ".jpeg", ".png"))

    async def validate_password(self, password: str, session: AsyncSession) -> bool:
        return bool(re.match(
            r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@#$/%^&+=!]).{8,}$",
            password))

    async def validate_otp(self, otp: str, session: AsyncSession) -> bool:
        if not otp:
            return False
        return bool(re.match(r"^\d{6}$", otp))

    async def validate_marital_status(self, marital_status: str, session: AsyncSession) -> bool:
        if not marital_status:
            return False
        return marital_status in ['Single', 'Married', 'Divorced', 'Widowed']

    async def validate_gender(self, gender: str, session: AsyncSession) -> bool:
        if not gender:
            return False
        return gender in ['Male', 'Female', 'Other']

    async def validate_date_of_birth(self, dob: date, session: AsyncSession) -> bool:
        if not date:
            return False
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age >= 18

    async def validate_annual_income(self, annual_income: str, session: AsyncSession) -> bool:
        valid_ranges = [
            "0 - 2,50,000",
            "2,50,001 - 5,00,000",
            "5,00,001 - 7,50,000",
            "7,50,001 - 10,00,000",
            "10,00,001 and above"
        ]
        return annual_income in valid_ranges

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

        ist = pytz.timezone("Asia/Kolkata")
        utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
        local_time = utc_time.astimezone(ist)
        local_time_naive = local_time.replace(tzinfo=None)

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
            create_at=local_time_naive,
            update_at=local_time_naive
        )

        session.add(new_policy)
        await session.commit()
        await session.refresh(new_policy)

        return new_policy


        

    async def upload_to_s3_bucket(self, file: UploadFile, folder_name: str) -> str:
        try:
            file_path = f"{folder_name}/{file.filename}"
            content_type, _ = mimetypes.guess_type(file.filename)  
            content_type = content_type or "application/octet-stream" 

            def upload():
                s3_client.put_object(
                    Bucket=BUCKET_NAME,
                    Key=file_path,
                    Body=file.file,
                    ContentType=content_type
                )

            await asyncio.to_thread(upload) 
            file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_path}"
            return file_url

        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file '{file.filename}' to S3: {e.response['Error']['Message']}"
            )

    async def delete_folder_contents(self, bucket_name: str, folder_name: str) -> bool:
        try:
            def list_objects():
                files = []
                continuation_token = None

                while True:
                    params = {"Bucket": bucket_name, "Prefix": folder_name}
                    if continuation_token:
                        params["ContinuationToken"] = continuation_token

                    response = s3_client.list_objects_v2(**params)

                    if "Contents" in response:
                        files.extend(response["Contents"])

                    if not response.get("IsTruncated"):
                        break

                    continuation_token = response.get("NextContinuationToken")

                return files

            def delete_files(files):
                """ Delete files in batches of 1000 (AWS limit). """
                for i in range(0, len(files), 1000):
                    batch = files[i : i + 1000]
                    file_keys = [{"Key": obj["Key"]} for obj in batch]
                    s3_client.delete_objects(Bucket=bucket_name, Delete={"Objects": file_keys})


            files_to_delete = await asyncio.to_thread(list_objects)

            if not files_to_delete:
                return True

            await asyncio.to_thread(delete_files, files_to_delete)

            return True

        except ClientError as e:
            return False
        

    async def create_policy_info(
        self,
        policy_info: PolicyeinfocreateRequest,
        photo: Optional[UploadFile],
        session: AsyncSession
    ):
        try:
            folder_name = f"Admin/PolicyInfo/INFO_{policy_info['policyinfo_name']}"

            photo_url = await self.upload_to_s3_bucket(photo, folder_name) if photo else None

            ist = pytz.timezone("Asia/Kolkata")
            utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
            local_time = utc_time.astimezone(ist)
            local_time_naive = local_time.replace(tzinfo=None)

            new_policy = policyinfo(
                policyinfo_name=policy_info['policyinfo_name'],
                photo=photo_url, 
                titledescription=policy_info['titledescription'],
                description=policy_info['description'],
                create_at=local_time_naive,
                update_at=local_time_naive
            )

            session.add(new_policy)
            await session.commit()

            return new_policy
        except Exception as e:
            await session.rollback()
            raise Exception(f"Error creating policy info: {str(e)}")


    async def policy_info_update(
        self,
        PolicyId,
        policy_infos: PolicyeinfocreateRequest,
        photos: Optional[UploadFile],
        session: AsyncSession
    ):
        photo_url = None
        try:
            if photos is not None:
                def extract_folder_name(url):
                    return "/".join(url.split("/")[3:-1])
                result = await session.execute(
                    select(policyinfo.photo).where(policyinfo.policyinfo_uid == PolicyId)
                )
                existing_photo_url = result.scalars().first()
                
                if not existing_photo_url:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, 
                        detail="Policy not found"
                    )
                folder_name = extract_folder_name(existing_photo_url)


                deletion = await self.delete_folder_contents(BUCKET_NAME, folder_name)
                if not deletion:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to delete folder '{folder_name}' from bucket '{BUCKET_NAME}'."
                    )
                photo_url = await self.upload_to_s3_bucket(photos, folder_name) if photos else None

            ist = pytz.timezone("Asia/Kolkata")
            utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
            local_time = utc_time.astimezone(ist)
            local_time_naive = local_time.replace(tzinfo=None)

            update_stmt = (
                update(policyinfo)
                .where(policyinfo.policyinfo_uid == PolicyId)
                .values(
                    policyinfo_name=policy_infos["policyinfo_name"],
                    titledescription=policy_infos["titledescription"],
                    description=policy_infos["description"],
                    photo=photo_url if photo_url else policyinfo.photo,
                    update_at=local_time_naive,
                )
            )

            await session.execute(update_stmt)
            await session.commit()

            return {"message": "Policy Info updated successfully"}
        except Exception as e:
            await session.rollback()
            raise Exception(f"Error creating policy info: {str(e)}")
        

    async def S3_busket_delete_file(self, existing_url, session: AsyncSession):
        try:
            def extract_folder_name(url):
                return "/".join(url.split("/")[3:-1])
            
            
            folder_name = extract_folder_name(existing_url)

            deletion = await self.delete_folder_contents(BUCKET_NAME, folder_name)
            if not deletion:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete folder '{folder_name}' from bucket '{BUCKET_NAME}'."
                )
            
            return True
        
        except Exception as e:
            await session.rollback()
            raise Exception(f"Error deleting policy info: {str(e)}")

    async def notification_update(self, user_id, message, session: AsyncSession):

        ist = pytz.timezone("Asia/Kolkata")
        utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
        local_time = utc_time.astimezone(ist)
        local_time_naive = local_time.replace(tzinfo=None)

        notification = Notification(
            user_id=user_id,
            message=message,
            create_at=local_time_naive
        )

        session.add(notification)
        await session.commit()
        await session.refresh(notification)

        return notification
