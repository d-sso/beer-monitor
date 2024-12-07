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

from sqlalchemy.orm import Session,selectinload
import logging

from typing import List, Tuple
from enum import Enum

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

asyncState = DetectApp(n_images = 100, saved_images=0, app_mode=AppModes.DETECT,user_id=1)

class Faces(BaseModel):
    """ This is a pydantic model to define the structure of the streaming data 
    that we will be sending the the cv2 Classifier to make predictions
    It expects a List of a Tuple of 4 integers
    """
    faces: List[Tuple[int, int, int, int]]
    app_state: DetectApp

### END todo

### TODO: refactor below parameters into dedicated config file
# by default store images on same folder
basePath = 'imgs/'
# default name of the images
baseName = 'img'
### END todo

logger = logging.getLogger('uvicorn.error')

# Async context manager controls the start/shutdown - https://fastapi.tiangolo.com/advanced/events/
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This tells fastapi to load the classifier upon app startup
    so that we don't have to wait for the classifier to be loaded after making a request
    """
    cascade_classifier.load(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    yield

Base.metadata.create_all(bind=engine)

logger = logging.getLogger(__name__)

app =FastAPI(lifespan=lifespan) # initialize FastAPI

cascade_classifier = cv2.CascadeClassifier() 

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


### SECTION for handling the web sockets and images
async def receive(websocket: WebSocket, queue: asyncio.Queue):
    """
    This is the asynchronous function that will be used to receive webscoket 
    connections from the web page
    """
    logger.info("Received")
    bytes = await websocket.receive_bytes()
    try:
        queue.put_nowait(bytes)
    except asyncio.QueueFull:
        pass

async def write_image(filename,image):
    cv2.imwrite(filename,image)

async def add_image():
    saved_images=saved_images+1

def check_face_size(img_height,img_width,x,y,width,height):
    """
    This function checks if the detected face is centered and has a minimum size
    """
    return x > img_width*1.0/4 and \
            y > img_height*1.0/6 and \
            (x + width) < img_width*3.0/4 and \
            (y + height) < img_height*5.0/6 and \
            width > 100 and \
            height > 150

async def detect(websocket: WebSocket, queue: asyncio.Queue, async_state: any):
    """
    This function takes the received request and sends it to our classifier
    which then goes through the data to detect the presence of a human face
    and returns the location of the face from the continous stream of visual data as a
    list of Tuple of 4 integers that will represent the 4 Sides of a rectangle
    """
    ### TODO: figure out best way to gracefully close connection
    while True:
        if async_state.app_mode == AppModes.DETECT:
            # detect mode - do the face detection
            bytes = await queue.get()
            data = np.frombuffer(bytes, dtype=np.uint8)
            img = cv2.imdecode(data, 1)
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            faces = cascade_classifier.detectMultiScale(gray)
            if len(faces) > 0:
                faces_output = Faces(faces=faces.tolist(),app_state=async_state)
            else:
                faces_output = Faces(faces=[],app_state=async_state)
            await websocket.send_text(faces_output.model_dump_json())
        elif async_state.app_mode == AppModes.CAPTURE:
            # program is in capture mode - do the capture & return to idle after
            bytes = await queue.get()
            data = np.frombuffer(bytes, dtype=np.uint8)
            img = cv2.imdecode(data, 1)
            [img_height,img_width,n] = img.shape
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            faces = cascade_classifier.detectMultiScale(gray)
            if len(faces) == 1:
                #Ensure we have a centered face and it's a big enough image:
                # Values returned for the Faces are {x, y, width, height}
                [x,y,width,height] = faces[0]
                if check_face_size(img_height=img_height,
                                   img_width=img_width,
                                   x=x,
                                   y=y,
                                   width=width,
                                   height=height):
                    # crop the image for the face only
                    img = img[y:(y + height),x:(x + width)]
                    async_state.saved_images = async_state.saved_images + 1
                    # use user_id as a folder to store the images
                    target_path = basePath + async_state.user_id + "/" + baseName + str(async_state.saved_images) + ".png"
                    logger.info("Saving at " + target_path)
                    # capture desired number of images
                    if async_state.saved_images < async_state.n_images:
                        await write_image(target_path,img)
                    else:
                        # after capturing images, go to idle mode
                        async_state.app_mode = AppModes.IDLE
                faces_output = Faces(faces=faces.tolist(),app_state=async_state)
            else:
                faces_output = Faces(faces=[],app_state=async_state)
            await websocket.send_text(faces_output.model_dump_json())
        else:
            # program is in idle mode - do nothing
            faces_output = Faces(faces=[],app_state=async_state)
            await websocket.send_text(faces_output.model_dump_json())

@app.websocket("/face-detection")
async def face_detection(websocket: WebSocket):
    """
    This is the endpoint that we will be sending request to from the 
    frontend
    """
    await websocket.accept()

    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    detect_task = asyncio.create_task(detect(websocket, queue,asyncState))

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