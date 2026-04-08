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


class UserUpdateSchema(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    nickname: Optional[str] = None


class DrinksSchemaFull(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: Optional[int]
    timestamp: datetime
    id: int
    quantity: float


class DrinkWithUser(BaseModel):
    """Drink record enriched with the owner's name — used for the paginated history endpoint."""
    id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    timestamp: datetime
    quantity: float


class PaginatedDrinks(BaseModel):
    items: List[DrinkWithUser]
    total: int
    page: int
    limit: int
    pages: int


class DrinkUpdateSchema(BaseModel):
    user_id: Optional[int] = None
    quantity: Optional[float] = None


class KegSchema(BaseModel):
    name: str
    keg_size: float
    density: Optional[float] = None
    image_url: Optional[str] = None


class KegUpdateSchema(BaseModel):
    name: Optional[str] = None
    keg_size: Optional[float] = None
    density: Optional[float] = None
    image_url: Optional[str] = None


class KegResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    keg_size: float
    density: Optional[float] = None
    active: bool = False
    image_url: Optional[str] = None


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