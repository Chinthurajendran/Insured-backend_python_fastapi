from sqlmodel import SQLModel, Field, Column,ForeignKey
from datetime import date, datetime
import uuid
import sqlalchemy.dialects.postgresql as pg
from enum import Enum as PyEnum
from sqlalchemy import Enum

class TransactionType(str, PyEnum):
    Debit = "debit"
    Credit = "credit"

class usertable(SQLModel, table=True):
    __tablename__ = "usertable"
    user_id: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID,
            nullable=False,
            primary_key=True,
            default=uuid.uuid4
        )
    )
    username: str
    email: str = Field(index=True)
    image: str = Field(default="")
    password: str = Field(default=None, nullable=True) 
    gender: str = Field(nullable=True)
    phone: str = Field(nullable=True)
    date_of_birth: date = Field(nullable=True)
    annual_income: str = Field(nullable=True)
    marital_status: str = Field(nullable=True)
    city: str = Field(max_length=100,nullable=True)
    latitude: float = Field(default=0.0)
    longitude: float = Field(default=0.0)
    policy_status: bool = Field(default=False)
    block_status: bool = Field(default=False)
    profile_status: bool = Field(default=False)
    delete_status: bool = Field(default=False)
    role: str = Field(default="user", max_length=20,nullable=False)
    create_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow))
    update_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow))

    def __repr__(self):
        return f"<UserTable {self.username}>"

class OTPVerification(SQLModel, table=True):
    __tablename__ = "otp_verification"
    
    otp_verification_uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, nullable=False, default=uuid.uuid4)
    )
    email: str = Field(index=True)
    otp: str = Field(nullable=True)
    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, nullable=False, default=datetime.utcnow)
    )
    updated_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, nullable=False, default=datetime.utcnow)
    )

    def __repr__(self):
        return f"<OTPVerification {self.message}>"


class Notification(SQLModel, table=True):
    __tablename__ = "notification"

    notification_uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, nullable=False, default=uuid.uuid4)
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(pg.UUID, ForeignKey("usertable.user_id"), nullable=False)
    )
    message: str = Field(default="", nullable=False)
    role: str = Field(default="user", max_length=20, nullable=False)
    delete_status: bool = Field(default=False)
    create_at: datetime = Field(sa_column=Column(
        pg.TIMESTAMP, default=datetime.utcnow))
    update_at: datetime = Field(sa_column=Column(
        pg.TIMESTAMP, default=datetime.utcnow))

    def __repr__(self):
        return f"<Notification {self.message}>"


class Wallet(SQLModel, table=True):
    __tablename__ = "wallet"
    
    transaction_uid: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID,
            nullable=False,
            primary_key=True,
            default=uuid.uuid4
        )
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(pg.UUID, ForeignKey("usertable.user_id"), nullable=False)
    )
    description: str = Field(default="", nullable=True)
    amount: int = Field(sa_column=Column(pg.INTEGER, nullable=False))
    transaction_type: TransactionType = Field(
        sa_column=Column(Enum(TransactionType), default=TransactionType.Debit)
    )
    role: str = Field(default="user", max_length=20, nullable=True)
    create_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow)
    )
    update_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    )

    def __repr__(self):
        return f"<Transaction {self.transaction_uid}>"