# main.py
import asyncio
import asyncio.log
import os
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

from sqlalchemy.orm import Session,selectinload
import logging

from typing import List, Tuple
from enum import Enum

import base64

import face_recognition_control

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
face_recognition_controller = face_recognition_control(logger)

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


### SECTION for handling the web sockets and images
async def receive(websocket: WebSocket, queue: asyncio.Queue):
    """
    This is the asynchronous function that will be used to receive webscoket 
    connections from the web page
    """
    logger.info("Received new image")
    base64img = await websocket.receive()
    try:
        base64img_split = base64img['text'].split(',')
        if base64img_split[0] == 'data:image/jpeg;base64':
            try:
                numpy_array = np.frombuffer(base64.b64decode(base64img_split[1]),np.uint8)
                queue.put_nowait(numpy_array)
            except asyncio.QueueFull:
                # drop queued items
                while not queue.empty():
                    queue.get_nowait()
                    queue.task_done()
                logger.info("Queue was full and flushed")
                pass
        else:
            logger.info('Received bad image')
    except Exception as e:
        logger.error("Error parsing data received - " + e)


async def detect(websocket: WebSocket, queue: asyncio.Queue, async_state: any, db:Session):
    """
    This function takes the received request and sends it to our classifier
    which then goes through the data to detect the presence of a human face
    and returns the location of the face from the continous stream of visual data as a
    list of Tuple of 4 integers that will represent the 4 Sides of a rectangle
    """
    ### TODO: figure out best way to gracefully close connection
    while True:
        try:
            if async_state.app_mode not in [AppModes.DETECT, AppModes.CAPTURE]:
                # program is in idle mode - do nothing
                faces_output = Faces(faces=[],app_state=async_state)
                await websocket.send_text(faces_output.model_dump_json())
            else:
                bytes = await queue.get()
                data = np.frombuffer(bytes, dtype=np.uint8)
                img = cv2.imdecode(data, cv2.IMREAD_COLOR)
                if img is not None:
                    faces = face_recognition_controller.recognize_faces(img)
                    if async_state.app_mode == AppModes.DETECT:
                        # detect mode - do the face detection
                        if len(faces) > 0:                           
                            # If there is just one identified user in the camera, set it as active
                            if len(faces["user_ids"]) == 1 and faces["user_ids"][0] != 0:
                                try:
                                    await set_active_user(faces["user_ids"][0],db)
                                except Exception as e:
                                    logger.error(f"Error setting user as active - {e}")

                            faces_output = Faces(faces=faces.tolist(),app_state=async_state,detected_face = (faces["user_ids"]))
                        else:
                            faces_output = Faces(faces=[],app_state=async_state,detected_face=[])
                        await websocket.send_text(faces_output.model_dump_json())

                    elif async_state.app_mode == AppModes.CAPTURE:

                        ### TODO: move this logic to face_recognition_control.py
                        # program is in capture mode - do the capture & return to idle after
                        [img_height,img_width,n] = img.shape
                        if len(faces) == 1:
                            #Ensure we have a centered face and it's a big enough image:
                            # Values returned for the Faces are {x, y, width, height}
                            [x,y,width,height] = faces[0]
                            if face_recognition_controller.check_face_size(img_height=img_height,
                                            img_width=img_width,
                                            x=x,
                                            y=y,
                                            width=width,
                                            height=height):
                                # crop the image for the face only
                                img = img[y:(y + height),x:(x + width)]
                                async_state.saved_images = async_state.saved_images + 1
                                # capture desired number of images
                                if async_state.saved_images < async_state.n_images:
                                    face_recognition_controller.encode_new_image(async_state.user_id,img)
                                else:
                                    # after capturing images, go to detect mode
                                    async_state.app_mode = AppModes.DETECT
                                    face_recognition_controller.save_images_on_buffer()
                            faces_output = Faces(faces=faces.tolist(),app_state=async_state,detected_face=[])
                        else:
                            faces_output = Faces(faces=[],app_state=async_state,detected_face=[])
                        await websocket.send_text(faces_output.model_dump_json())
                else:
                    logger.info("Empty image received")
        except Exception as e:
            logger.error(f"Error processing image - {e}")

@app.websocket("/face-detection")
async def face_detection(websocket: WebSocket,db: Session = Depends(get_db)):
    """
    This is the endpoint that we will be sending request to from the 
    frontend
    """
    await websocket.accept()

    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    detect_task = asyncio.create_task(detect(websocket, queue,asyncState,db))

    try:
        while True:
            await receive(websocket, queue)
    except WebSocketDisconnect:
        detect_task.cancel()
        await websocket.close()
    finally:
        detect_task.cancel()
        await websocket.close()

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