from sqlmodel import SQLModel, Field, Column, Field
from datetime import date, datetime
import uuid
import sqlalchemy.dialects.postgresql as pg


class policytable(SQLModel, table=True):
    __tablename__ = "policytable"
    policy_uid: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID,
            nullable=False,
            primary_key=True,
            default=uuid.uuid4
        )
    )
    policy_id: str = Field(unique=True, nullable=False)
    policy_name: str = Field(unique=True, nullable=False)
    policy_type: str = Field(nullable=False)

    id_proof: bool = Field(default=False)
    passbook: bool = Field(default=False)
    photo: bool = Field(default=False)
    pan_card: bool = Field(default=False)
    income_proof: bool = Field(default=False)
    nominee_address_proof: bool = Field(default=False)

    coverage: str = Field(nullable=False)
    settlement: str = Field(nullable=False)
    premium_amount: str = Field(nullable=False)

    age_group: str = Field(nullable=False)
    income_range: str = Field(nullable=False)

    description: str = Field(default="", nullable=True)

    create_at: datetime = Field(sa_column=Column(
        pg.TIMESTAMP, default=datetime.utcnow))
    update_at: datetime = Field(sa_column=Column(
        pg.TIMESTAMP, default=datetime.utcnow))

    def __repr__(self):
        return f"<policytable {self.Policy_name}>"
