from sqlalchemy import Column,Integer,String, Double, DateTime, ForeignKey,Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship,Mapped, mapped_column
from typing import List
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id:Mapped[int] = mapped_column(primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String)
    nickname = Column(String)
    active = Column(Boolean, default=False)

    drinks: Mapped[List["Drinks"]] = relationship(back_populates="user")

class Drinks(Base):
    __tablename__ = "drinks"

    id:Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="drinks")
    timestamp = Column(DateTime, server_default=func.now())
    quantity = Column(Double)
