from sqlmodel import SQLModel, Field, Column
from datetime import date, datetime
import uuid
import sqlalchemy.dialects.postgresql as pg

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
    password: str = Field(default=None, nullable=True)  # FIXED
    gender: str = Field(nullable=True)
    phone: str = Field(nullable=True)
    date_of_birth: date = Field(nullable=True)
    annual_income: int = Field(nullable=True)
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
