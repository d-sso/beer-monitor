from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserSchema(BaseModel):
    id: Optional[int] = None
    name: str
    email: Optional[str] = None
    nickname: Optional[str] = None


class DrinksSchema(BaseModel):
    user_id: int
    quantity: float


class DrinkQuantitySchema(BaseModel):
    quantity: float


class UserIDSchema(BaseModel):
    id: int


class DrinksSchemaFull(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    timestamp: datetime
    id: int
    quantity: float


class UserResponse(BaseModel):
    """Single user without drinks list — used for endpoints that return one user."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    active: bool = False


class UserWithDrinks(BaseModel):
    """User with full drinks list — used for the leaderboard endpoint."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    active: bool = False
    drinks: List[DrinksSchemaFull] = []