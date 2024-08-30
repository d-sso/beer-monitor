from typing import Optional
from datetime import datetime

from pydantic import BaseModel
from app.models import Drinks
from typing import List

class UserSchema(BaseModel):
    id: int
    name: str
    email: str
    nickname: str

class DrinksSchema(BaseModel):
    user_id: int
    quantity: float

class DrinkQuantitySchema(BaseModel):
    quantity: float

class UserIDSchema(BaseModel):
    id: int

class DrinksSchemaFull(BaseModel):
    user_id: int
    timestamp: datetime
    id: int
    quantity: float

class UserWithDrinks(BaseModel):
    id: int
    name: str
    email: str
    nickname: str
    active: bool
    drinks: List[DrinksSchemaFull] = []