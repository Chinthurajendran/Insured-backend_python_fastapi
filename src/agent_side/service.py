from .models import AgentTable
from .schemas import *
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from datetime import datetime
from src.utils import generate_passwd_hash,UPLOAD_DIR,random_code
import logging
import aiofiles
from fastapi import UploadFile,File,HTTPException,status
from dotenv import load_dotenv
import os
import boto3
import traceback
from src.admin_side.models import*
from src.user_side.models import*
from math import pow
import secrets
import string
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from src.utils import generate_passwd_hash,UPLOAD_DIR
from src.mail import mail_config
from botocore.exceptions import ClientError
import boto3
import pytz

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

class AgentService:

    async def get_agent_by_id(self,agent_id:str,session:AsyncSession):
        statement = select(AgentTable).where(AgentTable.agent_id == agent_id)
        result = await session.exec(statement)

        user = result.first()
        
        return user

    async def get_agent_by_agentid(self, agentid: str, session: AsyncSession):
        statement = select(AgentTable).where(AgentTable.agent_userid == agentid)
        result = await session.exec(statement)
        agent = result.first()
        return agent
    
    async def exist_agent_id(self,agent_id:str,session:AsyncSession):
        user = await self.get_agent_by_id(agent_id,session)

        return True if user is not None else False
    
    async def exist_agent_user_id(self,agent_id:str,session:AsyncSession):
        user = await self.get_agent_by_agentid(agent_id,session)

        return True if user is not None else False
    

    async def exist_email(self, agentid: str, session: AsyncSession):
        agents = await self.get_agent_by_agentid(agentid, session)
        return True if agents is not None else False

    async def create_user(
        self,
        agent_details: AgentCreateRequest,
        id_proof: UploadFile,
        session: AsyncSession
    ):
        agent_data_dict = agent_details.dict()

        ist = pytz.timezone("Asia/Kolkata")
        utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
        local_time = utc_time.astimezone(ist)
        local_time_naive = local_time.replace(tzinfo=None)

        create_at = local_time_naive
        update_at = local_time_naive

        folder_name = "Agent/"

        file_path = f"{folder_name}{id_proof.filename}"

        s3_client.upload_fileobj(id_proof.file, BUCKET_NAME, file_path)
        file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_path}"


        code = random_code()

        new_agent = AgentTable(
            agent_name=agent_data_dict["username"],
            agent_email=agent_data_dict["email"],
            phone=agent_data_dict["phone"],
            gender=agent_data_dict["gender"],
            date_of_birth=agent_data_dict["date_of_birth"],
            city=agent_data_dict["city"],
            agent_userid = f"AG{code}",
            password=generate_passwd_hash(agent_data_dict["password"]),
            agent_idproof= str (file_url),
            create_at=create_at,
            update_at=update_at
        )

        session.add(new_agent)
        await session.commit()
        await session.refresh(new_agent)

        logger.info(f"New user created: {new_agent.agent_name}")

        return new_agent


    async def profile_update(self, agent_data: AgentProfileCreateRequest, 
                             agentID, image: UploadFile, session: AsyncSession):
        try:
            if image is not None:
                folder_name = "Agent/Agnet Profile image/"

                file_path = f"{folder_name}{image.filename}"

                s3_client.upload_fileobj(image.file, BUCKET_NAME, file_path)
                file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_path}"

            result = await session.execute(select(AgentTable).where(AgentTable.agent_id == agentID))
            agent = result.scalars().first()

            if not agent:
                return {"error": "Agent not found"}

            agent.agent_name = agent_data.username
            agent.agent_email = agent_data.email
            agent.phone = agent_data.phone
            agent.gender = agent_data.gender
            agent.date_of_birth = agent_data.date_of_birth
            agent.city = agent_data.city
            if image is not None:
                agent.agent_profile = file_url 

            session.add(agent)
            await session.flush() 
            await session.commit()

            return {"message": "Profile updated successfully"}

        except Exception as e:
                await session.rollback() 
                traceback.print_exc() 
                return {"error": str(e)}


    async def ExistingUserPolicyCreation(self, agent_data: ExistingUserPolicyRequest, 
                                agentID, 
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
            
            folder_name = f"Agent/PolicyDocuments/EUPC{code}"

            id_proof_url = await upload_to_s3(id_proof, folder_name) if id_proof else None
            passbook_url = await upload_to_s3(passbook, folder_name) if passbook else None
            income_proof_url = await upload_to_s3(income_proof, folder_name) if income_proof else None
            photo_url = await upload_to_s3(photo, folder_name) if photo else None
            pan_card_url = await upload_to_s3(pan_card, folder_name) if pan_card else None
            nominee_address_proof_url = await upload_to_s3(nominee_address_proof, folder_name) if nominee_address_proof else None

            policy_result = await session.execute(select(policytable).where(policytable.policy_name == agent_data.policy_type))
            policys = policy_result.scalars().first()
            users_result = await session.execute(select(usertable).where(usertable.email == agent_data.email))
            users = users_result.scalars().first()

            ist = pytz.timezone("Asia/Kolkata")
            utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
            local_time = utc_time.astimezone(ist)
            local_time_naive = local_time.replace(tzinfo=None)

            create_at = local_time_naive
            update_at = local_time_naive
            date_of_payment = local_time_naive
            coverage = policys.coverage
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
                agent_id=agentID,
                policy_id=policys.policy_uid,
                policy_holder=users.username,
                email = users.email,
                gender = users.gender,
                phone = users.phone,
                marital_status = users.marital_status,
                city = users.city,
                policy_name=agent_data.policy_name,
                policy_type=agent_data.policy_type,
                nominee_name=agent_data.nominee_name,
                nominee_relationship=agent_data.nominee_relationship,
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
        
    async def create_newuser(self, user_details: NewUserPolicyRequest, session: AsyncSession):

        ist = pytz.timezone("Asia/Kolkata")
        utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
        local_time = utc_time.astimezone(ist)
        local_time_naive = local_time.replace(tzinfo=None)

        create_at = local_time_naive
        update_at = local_time_naive

        def generate_strong_password(length=10):
            alphabet = string.ascii_letters + string.digits + string.punctuation
            return ''.join(secrets.choice(alphabet) for _ in range(length))

        raw_password = generate_strong_password()
        hashed_password = generate_passwd_hash(raw_password)

        new_user = usertable(
            username=user_details.username,
            email=user_details.email,
            password=hashed_password, 
            gender=user_details.gender,
            phone=user_details.phone,
            date_of_birth=user_details.date_of_birth,
            annual_income=user_details.annual_income,
            marital_status=user_details.marital_status,
            city=user_details.city,
            create_at=create_at,
            update_at=update_at
        )

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        message = MessageSchema(
            subject="Your Account Details",
            recipients=[user_details.email],
            body=f"Hello {user_details.username},\n\n"
                f"Your account has been created successfully.\n\n"
                f"Here are your login credentials:\n"
                f"Email: {user_details.email}\n"
                f"Password: {raw_password} (Please change it after logging in.)\n\n"
                f"Best regards,\n"
                f"Your Team",
            subtype="plain"
        )

        fm = FastMail(mail_config)
        try:
            await fm.send_message(message)
            return new_user
        except Exception as e:
            print("Error sending email:", e)
            return {"error": "User created, but email failed to send."}


    async def delete_folder_contents(self, bucket_name, folder_name):
        try:

            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=folder_name)

            if 'Contents' not in response:
                print(f"No files found in '{folder_name}' in '{bucket_name}'.")
                return True

            file_keys = [{'Key': obj['Key']} for obj in response['Contents']]


            s3_client.delete_objects(Bucket=bucket_name, Delete={'Objects': file_keys})

            print(f"Deleted {len(file_keys)} files from '{folder_name}' in '{bucket_name}'.")
            return True
        except ClientError as e:
            print(f"Error deleting folder contents: {e.response['Error']['Message']}")
            return False

    async def upload_to_s3_bucket(self,file: UploadFile, folder_name: str) -> str:
        try:
            file_path = f"{folder_name}/{file.filename}"
            s3_client.upload_fileobj(file.file, BUCKET_NAME, file_path)
            file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_path}"
            return file_url
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file '{file.filename}' to S3: {str(e)}")
            
        

    async def Policyupdate(self, agent_data: NewUserPolicyRequest, 
                                PolicyId, 
                                id_proof: UploadFile,
                                passbook: UploadFile,
                                income_proof: UploadFile,
                                photo: UploadFile,
                                pan_card: UploadFile,
                                nominee_address_proof: UploadFile,
                                session: AsyncSession):
        try:

            PolicyDetails_reault = await session.execute(select(PolicyDetails).where(PolicyDetails.policydetails_uid == PolicyId))
            policysdetails = PolicyDetails_reault.scalars().first()

            def extract_folder_name(url):
                parts = url.split("/")
                folder_name = "/".join(parts[3:-1])
                return folder_name

            url = policysdetails.id_proof
            folder_name = extract_folder_name(url)

            deletion = await self.delete_folder_contents(BUCKET_NAME, folder_name)
            if not deletion:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete folder '{folder_name}' from bucket '{BUCKET_NAME}'."
                )


            id_proof_url = await self.upload_to_s3_bucket(id_proof, folder_name) if id_proof else None
            passbook_url = await self.upload_to_s3_bucket(passbook, folder_name) if passbook else None
            income_proof_url = await self.upload_to_s3_bucket(income_proof, folder_name) if income_proof else None
            photo_url = await self.upload_to_s3_bucket(photo, folder_name) if photo else None
            pan_card_url = await self.upload_to_s3_bucket(pan_card, folder_name) if pan_card else None
            nominee_address_proof_url = await self.upload_to_s3_bucket(nominee_address_proof, folder_name) if nominee_address_proof else None

            policy_result = await session.execute(select(policytable).where(policytable.policy_name == agent_data.policy_type))
            policys = policy_result.scalars().first()

            ist = pytz.timezone("Asia/Kolkata")
            utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
            local_time = utc_time.astimezone(ist)
            local_time_naive = local_time.replace(tzinfo=None)

            update_at = local_time_naive
            date_of_payment = local_time_naive
            coverage = policys.coverage
            settlement = policys.settlement
            premium_amount = float(policys.premium_amount)  

            dob = agent_data.date_of_birth
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

            r = 0.06  
            n = 12  
            t = int(coverage) - age 

            if t > 0: 
                monthly_payment = (premium_amount * (r / n)) / (1 - pow(1 + (r / n), -n * t))
            else:
                monthly_payment = premium_amount / 12  

            policysdetails.policy_holder=agent_data.username
            policysdetails.email=agent_data.email
            policysdetails.gender=agent_data.gender
            policysdetails.phone=agent_data.phone
            policysdetails.marital_status=agent_data.marital_status
            policysdetails.city=agent_data.city
            policysdetails.policy_name=agent_data.policy_name
            policysdetails.policy_type=agent_data.policy_type
            policysdetails.nominee_name=agent_data.nominee_name
            policysdetails.nominee_relationship=agent_data.nominee_relationship
            policysdetails.income_range=agent_data.annual_income
            policysdetails.monthly_amount=monthly_payment
            policysdetails.age=str(age)
            policysdetails.date_of_birth=agent_data.date_of_birth
            policysdetails.id_proof=id_proof_url
            policysdetails.passbook=passbook_url
            policysdetails.photo=photo_url
            policysdetails.pan_card=pan_card_url
            policysdetails.income_proof=income_proof_url
            policysdetails.nominee_address_proof=nominee_address_proof_url
            policysdetails.date_of_payment=date_of_payment
            policysdetails.policy_status=ApprovalStatus.processing
            policysdetails.update_at=update_at

            await session.commit()

            return {"message": "Profile updated successfully"}

        except Exception as e:
            await session.rollback()
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": f"An error occurred: {str(e)}"}
            )
            