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
    gender: str = Field(default='Male', nullable=True)
    phone: str = Field(default="7034345848")
    date_of_birth: date = Field(default=date(1997, 12, 15), nullable=True)
    annual_income: int = Field(default=500000)
    marital_status: str = Field(default='Single', nullable=True)
    city: str = Field(default="Kochi", max_length=100)
    latitude: float = Field(default=0.0)
    longitude: float = Field(default=0.0)
    policy_status: bool = Field(default=False)
    block_status: bool = Field(default=False)
    profile_status: bool = Field(default=False)
    delete_status: bool = Field(default=False)
    is_admin: bool = Field(default=False)
    create_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow))
    update_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow))

    def __repr__(self):
        return f"<UserTable {self.username}>"
