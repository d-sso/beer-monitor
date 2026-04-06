# main.py
import asyncio
import asyncio.log

from contextlib import asynccontextmanager
import cv2
import numpy as np

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.models import Base, User, Drinks
from app.schemas import UserSchema, DrinksSchema, DrinkQuantitySchema,UserWithDrinks
from app.database import engine, SessionLocal
from pydantic import BaseModel
import ssl

from sqlalchemy.orm import Session,selectinload
import logging

from typing import List, Tuple
from enum import Enum

import base64

import app.face_recognition_control as face_recognition_control

### TODO: refactor below portion into different file
class AppModes(Enum):
    IDLE = 0
    CAPTURE = 1
    DETECT = 2

### TODO: Creating a new object and assigning properties - probably better to refator into a class in a different file
class DetectApp(BaseModel):
    n_images: int
    saved_images: int
    app_mode: AppModes
    user_id: int

asyncState = DetectApp(n_images = 10, saved_images=0, app_mode=AppModes.DETECT,user_id=1)

class Faces(BaseModel):
    """ This is a pydantic model to define the structure of the streaming data 
    that we will be sending the the cv2 Classifier to make predictions
    It expects a List of a Tuple of 4 integers
    """
    faces: List[Tuple[int, int, int, int]]
    detected_face: List[int]
    app_state: DetectApp

### END todo
Base.metadata.create_all(bind=engine)

logger = logging.getLogger(__name__)
#logger = logging.getLogger('uvicorn.error')
face_recognition_controller = face_recognition_control.face_recognition_controller(logger)

# Async context manager controls the start/shutdown - https://fastapi.tiangolo.com/advanced/events/
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This tells fastapi to load the classifier upon app startup
    so that we don't have to wait for the classifier to be loaded after making a request
    """
    #try:
    #    face_recognition_controller = face_recognition_control(logger)
    #except Exception as e:
    #    logger.error(f"Could not load model - {e}")
    yield

app =FastAPI(lifespan=lifespan) # initialize FastAPI
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain(
    "C:/Users/vihud/OneDrive/Documentos/Projects/PythonDev/KegaratorApp/beer-monitor/api/certificate/cert.pem"
    ,keyfile="C:/Users/vihud/OneDrive/Documentos/Projects/PythonDev/KegaratorApp/beer-monitor/api/certificate/key.pem"
    )

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

### Commented out get "/" as app will be serving static files
#@app.get("/")
#async def root():
    #return {"message": "Hello World"}

@app.post("/adduser")
async def add_user(request:UserSchema, db: Session = Depends(get_db)):
    # check if user already exists
    user = db.query(User).filter(User.name == request.name).first()
    if user:
        asyncState.app_mode = AppModes.DETECT
        logger.info("User already exists")
        return user
    
    user = User(name = request.name, email = request.email, nickname = request.nickname)
    db.add(user)
    db.commit()
    db.refresh(user)
    asyncState.app_mode = AppModes.CAPTURE
    asyncState.user_id = user.id
    asyncState.saved_images = 0

    return user

@app.get("/users")
async def get_users(db: Session = Depends(get_db)):
    users = db.query(User).options(selectinload(User.drinks)).all()
    return users

@app.get("/user/active")
async def get_active_user(db: Session = Depends(get_db)):
    user = db.query(User).filter(User.active == True).first()
    return user

async def set_active_user(id,db: Session):
    logger.info(f"Setting active user: {id}")
    user = db.query(User).get(int(id))
    if not user.active:
        currentActive = db.query(User).filter(User.active == True).first()
        if currentActive:
            currentActive.active = False
        user.active = True
        db.commit()
        db.refresh(user)
    return user

@app.put("/user/active/{id}")
async def endpoint_set_active_user(id,db: Session = Depends(get_db)):
    return set_active_user(id,db)

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


import redis
import json

# Redis configuration
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
r = redis.from_url(redis_url)

### SECTION for handling the web sockets and images
async def receive(websocket: WebSocket):
    """
    This is the asynchronous function that will be used to receive webscoket 
    connections from the web page
    """
    base64img = await websocket.receive()
    try:
        base64img_split = base64img['text'].split(',')
        if base64img_split[0] == 'data:image/jpeg;base64':
            try:
                # Push the raw base64 decoded bytes to redis queue
                image_bytes = base64.b64decode(base64img_split[1])
                # We can limit the queue size by checking length first or just lpush
                # Using a fixed queue name 'frame_queue'
                r.lpush('frame_queue', image_bytes)
                r.ltrim('frame_queue', 0, 10) # Keep only 10 frames in queue
            except Exception as e:
                logger.error(f"Error pushing to redis: {e}")
        else:
            logger.info('Received bad image format')
    except Exception as e:
        logger.error(f"Error parsing data received - {e}")


async def detect(websocket: WebSocket, async_state: any):
    """
    This function retrieves the latest detection results from Redis
    and sends them to the frontend
    """
    while True:
        try:
            # Periodically check Redis for the latest face locations/ids
            last_results = r.get('last_face_locations')
            if last_results:
                results = json.loads(last_results)
                faces_output = Faces(
                    faces=results.get('face_locations', []),
                    app_state=async_state,
                    detected_face=results.get('user_ids', [])
                )
                await websocket.send_text(faces_output.model_dump_json())
            
            # Small delay to not overwhelm the websocket with redundant data
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in detect loop - {e}")
            await asyncio.sleep(1)

@app.websocket("/face-detection")
async def face_detection(websocket: WebSocket,db: Session = Depends(get_db)):
    """
    This is the endpoint that we will be sending request to from the 
    frontend
    """
    await websocket.accept()

    detect_task = asyncio.create_task(detect(websocket, asyncState))

    try:
        while True:
            await receive(websocket)
    except WebSocketDisconnect:
        detect_task.cancel()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        detect_task.cancel()
        # await websocket.close() # Might already be closed

@app.post("/recordFace")
async def record_face(id):
    """
    This function toggles the app behavior, so it starts capturing data
    """
    asyncState.app_mode = AppModes.CAPTURE
    asyncState.saved_images = 0
    asyncState.user_id = id
    return asyncState

@app.post("/detectFace")
async def detect_face():
    """
    This function toggles the app behavior, so it starts capturing data
    """
    asyncState.app_mode = AppModes.DETECT
    asyncState.saved_images = 0
    asyncState.user_id = 0
    return asyncState

app.mount("/", StaticFiles(directory="static"), name="static")