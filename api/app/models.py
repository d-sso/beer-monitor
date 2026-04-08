from sqlalchemy import Column,Integer,String, Double, DateTime, ForeignKey,Boolean, LargeBinary
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship,Mapped, mapped_column
from typing import List, Optional
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id:Mapped[int] = mapped_column(primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String)
    nickname = Column(String)
    active = Column(Boolean, default=False)
    face_encoding = Column(LargeBinary, nullable=True)

    drinks: Mapped[List["Drinks"]] = relationship(back_populates="user", passive_deletes=True)

class Drinks(Base):
    __tablename__ = "drinks"

    id:Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user: Mapped[Optional["User"]] = relationship(back_populates="drinks")
    timestamp = Column(DateTime, default=datetime.utcnow)
    quantity = Column(Double)
