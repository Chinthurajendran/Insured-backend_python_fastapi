from .models import *
from .schemas import *
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from datetime import datetime
from src.utils import generate_passwd_hash, UPLOAD_DIR, random_code
from fastapi import UploadFile, File, HTTPException, status, WebSocket, WebSocketDisconnect
import logging
from uuid import UUID
import traceback
from dotenv import load_dotenv
import os
import boto3
from src.admin_side.models import *
import pytz
import razorpay
import hmac
import hashlib
from src.messages.connetct_manager import connection_manager
from fastapi import Query
import re

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
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
    
    async def validate_city(self, text: str, session: AsyncSession) -> bool:
        if not text:
            return False
        return bool(re.match(r"^[A-Za-z\s]+$", text))

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



class UserService:
    async def get_user_by_id(self, user_id: str, session: AsyncSession):
        statement = select(usertable).where(usertable.user_id == user_id)
        result = await session.exec(statement)

        user = result.first()

        return user

    async def get_user_by_email(self, email: str, session: AsyncSession):
        statement = select(usertable).where(usertable.email == email)
        result = await session.exec(statement)

        user = result.first()

        return user

    async def get_user_by_username(self, username: str, session: AsyncSession):
        statement = select(usertable).where(usertable.username == username)

        result = await session.exec(statement)
        user = result.first()
        return user

    async def exist_email(self, email: str, session: AsyncSession):
        user = await self.get_user_by_email(email, session)

        return True if user is not None else False

    async def exist_username(self, username: str, session: AsyncSession):
        user = await self.get_user_by_username(username, session)

        return True if user is not None else False

    async def exist_user_id(self, user_id: str, session: AsyncSession):
        user = await self.get_user_by_id(user_id, session)

        return True if user is not None else False

    async def create_user(self, user_details: UserCreate, session: AsyncSession):

        user_data_dict = user_details.model_dump()

        ist = pytz.timezone("Asia/Kolkata")
        utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
        local_time = utc_time.astimezone(ist)
        local_time_naive = local_time.replace(tzinfo=None)

        create_at = local_time_naive
        update_at = local_time_naive

        new_user = usertable(
            **user_data_dict,
            create_at=create_at,
            update_at=update_at
        )
        new_user.password = generate_passwd_hash(user_data_dict['password'])

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        return new_user

    async def profile_update(
        self,
        user_data: ProfileCreateRequest,
        user_Id: UUID,
        image: Optional[UploadFile],
        session: AsyncSession
    ):
        try:
            file_url = None
            if image:
                folder_name = "Users/"
                file_path = f"{folder_name}{image.filename}"
                s3_client.upload_fileobj(image.file, BUCKET_NAME, file_path)
                file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_path}"

            result = await session.execute(
                select(usertable).where(usertable.user_id == user_Id)
            )
            user = result.scalars().first()

            if not user:
                return {"error": "User not found"}

            for field in user_data.__dict__:
                setattr(user, field, getattr(user_data, field))

            if file_url:
                user.image = file_url

            user.profile_status = True

            session.add(user)
            await session.commit()

            return {"message": "Profile updated successfully"}

        except Exception as e:
            await session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update profile: {str(e)}"
            )

    async def PolicyCreation(self,
                             user_data: PolicyRegistration,
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
            age = today.year - dob.year - \
                ((today.month, today.day) < (dob.month, dob.day))

            r = 0.06
            n = 12
            t = int(coverage) - age

            if t > 0:
                monthly_payment = (premium_amount * (r / n)) / \
                    (1 - pow(1 + (r / n), -n * t))
            else:
                monthly_payment = premium_amount / 12

            new_policy = PolicyDetails(
                user_id=users.user_id,
                policy_id=policys.policy_uid,
                policy_holder=users.username,
                email=users.email,
                gender=users.gender,
                phone=users.phone,
                marital_status=users.marital_status,
                city=users.city,
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
                date_of_birth=users.date_of_birth,
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

            message = "Your policy has been submitted successfully. Thank you for registering!"
            notification = await self.notification_update(users.user_id, message, session)

            if not notification:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail="Failed to create notification")
            await session.flush()
            await session.commit()

            return {"message": "Policy updated successfully"}

        except Exception as e:
            await session.rollback()
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": f"An error occurred: {str(e)}"}
            )

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

    async def payment_creation(self, order_data, session: AsyncSession):
        try:
            order = client.order.create(order_data)
            return {
                "order_id": order["id"],
                "amount": order["amount"],
                "currency": order["currency"]
            }

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Payment creation failed: {str(e)}")

    async def payment_verification(
        self,
        PolicyId: UUID,
        request_data: PaymentVerificationRequest,
        session: AsyncSession
    ) -> bool:
        try:
            generated_signature = hmac.new(
                RAZORPAY_KEY_SECRET.encode(),
                f"{request_data.order_id}|{request_data.payment_id}".encode(),
                hashlib.sha256
            ).hexdigest()

            ist = pytz.timezone("Asia/Kolkata")
            utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
            local_time = utc_time.astimezone(ist).replace(tzinfo=None)

            if hmac.compare_digest(generated_signature, request_data.signature):

                transaction = Transaction(
                    policy_id=PolicyId,
                    amount=int(request_data.amount) // 100,
                    description="Paid insurance amount",
                    create_at=local_time,
                    update_at=local_time
                )

                policy_data = await session.execute(select(PolicyDetails).where(PolicyDetails.policydetails_uid == PolicyId))
                policys = policy_data.scalars().first()

                message = f"₹{int(request_data.amount) // 100} has been successfully paid towards your policy."
                notification = await self.notification_update(policys.user_id, message, session)

                if not policys:
                    raise HTTPException(
                        status_code=404, detail="Policy not found")
                policys.payment_status = True

                session.add(transaction)
                await session.commit()
                await session.refresh(transaction)

                return True

            return False

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Payment verification failed: {str(e)}")

    async def wallet_payment_add(
        self,
        userId: UUID,
        request_data: PaymentVerificationRequest,
        session: AsyncSession
    ) -> bool:
        try:
            generated_signature = hmac.new(
                RAZORPAY_KEY_SECRET.encode(),
                f"{request_data.order_id}|{request_data.payment_id}".encode(),
                hashlib.sha256
            ).hexdigest()

            ist = pytz.timezone("Asia/Kolkata")
            utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
            local_time = utc_time.astimezone(ist).replace(tzinfo=None)

            if hmac.compare_digest(generated_signature, request_data.signature):

                transaction = Wallet(
                    user_id=userId,
                    amount=int(request_data.amount) // 100,
                    description="Amount Add",
                    transaction_type="debit",
                    create_at=local_time,
                    update_at=local_time
                )

                message = f"You've successfully added ₹{int(request_data.amount) // 100} to your wallet. Happy spending!"
                notification = await self.notification_update(userId, message, session)

                session.add(transaction)
                await session.commit()
                await session.refresh(transaction)

                return True

            return False

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Payment verification failed: {str(e)}")

    async def wallet_payment_withdraw(
        self,
        userId: UUID,
        request_data: PaymentVerificationRequest,
        transaction_type: str,
        session: AsyncSession,
        policy_id: Optional[UUID] = Query(None)
    ) -> bool:
        try:
            generated_signature = hmac.new(
                RAZORPAY_KEY_SECRET.encode(),
                f"{request_data.order_id}|{request_data.payment_id}".encode(),
                hashlib.sha256
            ).hexdigest()

            ist = pytz.timezone("Asia/Kolkata")
            utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
            local_time = utc_time.astimezone(ist).replace(tzinfo=None)

            if hmac.compare_digest(generated_signature, request_data.signature):
                if transaction_type == 'withdraw':

                    transaction = Wallet(
                        user_id=userId,
                        amount=int(request_data.amount) // 100,
                        description="Amount withdraw",
                        transaction_type="credit",
                        create_at=local_time,
                        update_at=local_time
                    )
                    amount = int(request_data.amount) // 100
                    message = f"₹{amount} has been successfully withdrawn from your wallet!"
                    notification = await self.notification_update(userId, message, session)
                else:
                    transaction = Wallet(
                        user_id=userId,
                        amount=int(request_data.amount) // 100,
                        description="Paid insurance amount",
                        transaction_type="credit",
                        create_at=local_time,
                        update_at=local_time
                    )
                    amount = int(request_data.amount) // 100,
                    message = f"₹{amount} has been successfully deducted from your wallet for policy payment. Your policy is now active."
                    notification = await self.notification_update(userId, message, session)
                    policy_data = await session.execute(select(PolicyDetails).where(PolicyDetails.policydetails_uid == policy_id))
                    policys = policy_data.scalars().first()

                    if not policys:
                        raise HTTPException(
                            status_code=404, detail="Policy not found")
                    policys.payment_status = True

                session.add(transaction)
                await session.commit()
                await session.refresh(transaction)

                return True

            return False

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Payment verification failed: {str(e)}")
