# main.py
import asyncio
import asyncio.log
import os
from contextlib import asynccontextmanager
import cv2
import numpy as np
import pickle
import face_recognition

from pathlib import Path
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

### TODO: refactor below parameters into dedicated config file
# by default store images on same folder
basePath = 'C:/Users/vihud/OneDrive/Documentos/Projects/PythonDev/DetectFace/imgs/'
# default name of the images
baseName = 'img'
encodings_file_path = 'C:\\Users\\vihud\\OneDrive\\Documentos\\Projects\\PythonDev\\DetectFace\\saved_encodings'
all_encodings = []
encoding_user_ids = []
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
    try:
        with open(encodings_file_path,"rb") as saved_encodings:
            loaded_encodings = pickle.load(saved_encodings)
            for encoding in loaded_encodings:
                for item in encoding['encodings']:
                    all_encodings.append(item)
                    encoding_user_ids.append(encoding['userId'])
    except Exception as e:
        logger.error(f"Could not load model - {e}")
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
    asyncState.app_mode = AppModes.CAPTURE
    asyncState.user_id = user.id
    target_path = basePath + str(asyncState.user_id)
    try:
        os.mkdir(target_path)
    except FileExistsError:
        print(f"Directory '{target_path}' already exists.")
    except PermissionError:
        print(f"Permission denied: Unable to create '{target_path}'.")
        asyncState.app_mode = AppModes.DETECT
    except Exception as e:
        print(f"An error ocurred - can't capture images: {e}")
        asyncState.app_mode = AppModes.DETECT

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
    logger.info("Received")
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

def is_number(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

async def train_model():
    folderPath = Path(basePath)

    pathlist = [x for x in folderPath.iterdir() if x.is_dir()]
    all_encodings = []
    encoding_user_ids = []

    saved_encodings = []

    for path in pathlist:
        encodings = []
        userId = path.name
        if is_number(userId):
            for file in path.glob('**/*.png'):
                with open(file,"rb") as tst:
                    f = tst.read()
                    img = np.asarray(bytearray(f))
                image = face_recognition.load_image_file(file)
                face_encoding = face_recognition.face_encodings(image)
                if len(face_encoding) > 0:
                    encodings.append(face_encoding[0])
        user_encodings = {
            'userId': userId,
            'encodings': encodings
        }
        saved_encodings.append(user_encodings)

    for encoding in saved_encodings:
        for item in encoding['encodings']:
            all_encodings.append(item)
            encoding_user_ids.append(encoding['userId'])

    with open(encodings_file_path,"wb") as fp:
        pickle.dump(saved_encodings,fp)

## TODO: Improve method of adding new encodings, just add the new one instead of going through all of them, like below
## need to redesign how the model is trained/saved
async def train_model_for_new_user(userId):
    folderPath = Path(basePath + userId)

    pathlist = [x for x in folderPath.iterdir() if x.is_dir()]

    with folderPath as path:
        encodings = []
        if is_number(userId):
            for file in path.glob('**/*.png'):
                with open(file,"rb") as tst:
                    f = tst.read()
                    img = np.asarray(bytearray(f))
                image = face_recognition.load_image_file(file)
                face_encoding = face_recognition.face_encodings(image)[0]
                all_encodings.append(face_encoding)
                encoding_user_ids.append(userId)


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
                    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
                    ## TODO: remove the face classifier below, the "face_recognition" one seems to work better
                    faces = cascade_classifier.detectMultiScale(gray)
                    if async_state.app_mode == AppModes.DETECT:
                        # detect mode - do the face detection
                        if len(faces) > 0:
                            face_locations = face_recognition.face_locations(img)
                            face_encodings = face_recognition.face_encodings(img,face_locations)
                            user_ids_in_image = []
                            for face in face_encodings:
                                matches = face_recognition.compare_faces(all_encodings,face)
                                i = 0
                                while i<len(matches) and not matches[i]:
                                    i = i+1
                                user_ids_in_image.append(0 if i==len(matches) else encoding_user_ids[i])
                            
                            # If there is just one identified user in the camera, set it as active
                            if len(user_ids_in_image) == 1 and user_ids_in_image[0] != 0:
                                try:
                                    await set_active_user(user_ids_in_image[0],db)
                                except Exception as e:
                                    logger.error(f"Error recognizing user - {e}")

                            faces_output = Faces(faces=faces.tolist(),app_state=async_state,detected_face = (user_ids_in_image))
                        else:
                            faces_output = Faces(faces=[],app_state=async_state,detected_face=[])
                        await websocket.send_text(faces_output.model_dump_json())
                    elif async_state.app_mode == AppModes.CAPTURE:
                        # program is in capture mode - do the capture & return to idle after
                        [img_height,img_width,n] = img.shape
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
                                target_path = basePath + str(async_state.user_id) + "/" + baseName + str(async_state.saved_images) + ".png"
                                logger.info("Saving at " + target_path)
                                # capture desired number of images
                                if async_state.saved_images < async_state.n_images:
                                    await write_image(target_path,img)
                                else:
                                    # after capturing images, go to detect mode
                                    async_state.app_mode = AppModes.DETECT
                                    await train_model()
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