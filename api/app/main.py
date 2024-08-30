# main.py

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models import Base, User, Drinks
from app.schemas import UserSchema, DrinksSchema, DrinkQuantitySchema,UserWithDrinks
from app.database import engine, SessionLocal
from sqlalchemy.orm import Session,selectinload
import logging

Base.metadata.create_all(bind=engine)

logger = logging.getLogger(__name__)

app = FastAPI()

origins = ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/adduser")
async def add_user(request:UserSchema, db: Session = Depends(get_db)):
    user = User(name = request.name, email = request.email, nickname = request.nickname)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.get("/users")
async def get_users(db: Session = Depends(get_db)):
    users = db.query(User).options(selectinload(User.drinks)).all()
    return users

@app.get("/user/active")
async def get_active_user(db: Session = Depends(get_db)):
    user = db.query(User).filter(User.active == True).first()
    return user

@app.put("/user/active/{id}")
async def set_active_user(id,db: Session = Depends(get_db)):
    logger.info(id)
    user = db.query(User).get(int(id))
    if not user.active:
        currentActive = db.query(User).filter(User.active == True).first()
        if currentActive:
            currentActive.active = False
        user.active = True
        db.commit()
        db.refresh(user)
    return user

@app.get("/user/{user_name}")
async def get_users(user_name, db: Session = Depends(get_db)):
    users = db.query(User).filter(User.name == user_name).first()
    return users


@app.get("/drinks")
async def get_drinks(db: Session = Depends(get_db)):
    users = db.query(Drinks).all()
    return users

@app.post("/addDrink")
async def add_drink(request:DrinksSchema, db: Session = Depends(get_db)):
    drink = Drinks(user_id=request.user_id,quantity=request.quantity)
    print(request.quantity)
    db.add(drink)
    db.commit()
    db.refresh(drink)
    return drink

@app.post("/addDrinkToActiveUser")
async def add_drink(request:DrinkQuantitySchema, db: Session = Depends(get_db)):
    currentActive = db.query(User).filter(User.active == True).first()
    drink = Drinks(user_id=currentActive.id,quantity=request.quantity)
    print(request.quantity)
    db.add(drink)
    db.commit()
    db.refresh(drink)
    return drink