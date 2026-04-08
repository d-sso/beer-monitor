# main.py
import os
import asyncio
import asyncio.log

from contextlib import asynccontextmanager
import cv2
import numpy as np

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.models import Base, User, Drinks, Keg
from sqlalchemy.orm import selectinload
from app.schemas import UserSchema, DrinksSchema, DrinkQuantitySchema, UserResponse, UserWithDrinks, UserUpdateSchema, PaginatedDrinks, DrinkWithUser, DrinkUpdateSchema, KegSchema, KegUpdateSchema, KegResponse
from app.database import engine, SessionLocal
from pydantic import BaseModel
import ssl

from sqlalchemy.orm import Session,selectinload
import logging

from typing import List, Optional, Tuple
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

class LatestDrink(BaseModel):
    user_name: Optional[str] = None
    quantity: float
    timestamp: str

class KegInfo(BaseModel):
    keg_size: float
    name: str
    image_url: Optional[str] = None

class Faces(BaseModel):
    """ This is a pydantic model to define the structure of the streaming data
    that we will be sending the the cv2 Classifier to make predictions
    It expects a List of a Tuple of 4 integers
    """
    faces: List[Tuple[int, int, int, int]]
    detected_face: List[int]
    app_state: DetectApp
    latest_drinks: List[LatestDrink] = []
    current_pour: float = 0.0
    remaining_beer_l: Optional[float] = None
    active_keg: Optional[KegInfo] = None

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
cert_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "certificate", "cert.pem")
key_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "certificate", "key.pem")

if os.path.exists(cert_path) and os.path.exists(key_path):
    ssl_context.load_cert_chain(cert_path, keyfile=key_path)
else:
    logger.warning(f"Certificates not found at {cert_path} or {key_path}. SSL might not be enabled.")

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

@app.post("/adduser", response_model=UserResponse)
async def add_user(request:UserSchema, db: Session = Depends(get_db)):
    # check if user already exists
    user = db.query(User).filter(User.name == request.name).first()
    if user:
        asyncState.app_mode = AppModes.DETECT
        logger.info(f"User already exists: '{request.name}' (ID: {user.id})")
        _write_app_state()
        return user

    user = User(name = request.name, email = request.email, nickname = request.nickname)
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"User created: '{user.name}' (ID: {user.id}, nickname: '{user.nickname}')")
    asyncState.app_mode = AppModes.CAPTURE
    asyncState.user_id = user.id
    asyncState.saved_images = 0
    _write_app_state()
    logger.info(f"Switched to CAPTURE mode for user_id={user.id}, capturing {asyncState.n_images} images")

    return user

@app.get("/users", response_model=List[UserWithDrinks])
async def get_users(db: Session = Depends(get_db)):
    users = db.query(User).options(selectinload(User.drinks)).all()
    return users

@app.get("/user/active", response_model=Optional[UserResponse])
async def get_active_user(db: Session = Depends(get_db)):
    user = db.query(User).filter(User.active == True).first()
    return user

async def set_active_user(id,db: Session):
    user = db.get(User, int(id))
    if user and not user.active:
        currentActive = db.query(User).filter(User.active == True).first()
        prev = f"'{currentActive.name}'" if currentActive else "none"
        if currentActive:
            currentActive.active = False
        user.active = True
        db.commit()
        db.refresh(user)
        logger.info(f"Active user changed: {prev} -> '{user.name}' (ID: {user.id})")
    else:
        logger.debug(f"set_active_user: user '{getattr(user, 'name', id)}' already active or not found")
    return user

@app.put("/user/active/{id}", response_model=Optional[UserResponse])
async def endpoint_set_active_user(id,db: Session = Depends(get_db)):
    return await set_active_user(id,db)

@app.get("/user/{user_name}", response_model=Optional[UserResponse])
async def get_user_by_name(user_name, db: Session = Depends(get_db)):
    users = db.query(User).filter(User.name == user_name).first()
    return users

@app.patch("/user/{id}", response_model=UserResponse)
async def update_user(id: int, request: UserUpdateSchema, db: Session = Depends(get_db)):
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if request.name is not None:
        user.name = request.name
    if request.email is not None:
        user.email = request.email
    if request.nickname is not None:
        user.nickname = request.nickname
    db.commit()
    db.refresh(user)
    logger.info(f"User updated: ID={id}, name='{user.name}'")
    return user

@app.delete("/user/{id}", status_code=204)
async def delete_user(id: int, db: Session = Depends(get_db)):
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    logger.info(f"User deleted: ID={id}")


@app.get("/drinks", response_model=PaginatedDrinks)
async def get_drinks(page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    query = db.query(Drinks).order_by(Drinks.timestamp.desc())
    total = query.count()
    offset = (page - 1) * limit
    rows = query.offset(offset).limit(limit).all()
    pages = max(1, (total + limit - 1) // limit)
    items = [
        DrinkWithUser(
            id=d.id,
            user_id=d.user_id,
            user_name=d.user.name if d.user else None,
            timestamp=d.timestamp,
            quantity=d.quantity,
        )
        for d in rows
    ]
    return PaginatedDrinks(items=items, total=total, page=page, limit=limit, pages=pages)

@app.patch("/drink/{id}")
async def update_drink(id: int, request: DrinkUpdateSchema, db: Session = Depends(get_db)):
    drink = db.get(Drinks, id)
    if not drink:
        raise HTTPException(status_code=404, detail="Drink not found")
    if request.user_id is not None:
        user = db.get(User, request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        drink.user_id = request.user_id
    if request.quantity is not None:
        drink.quantity = request.quantity
    db.commit()
    db.refresh(drink)
    logger.info(f"Drink updated: ID={id}, user_id={drink.user_id}, quantity={drink.quantity}")
    return drink

@app.post("/addDrink")
async def add_drink(request:DrinksSchema, db: Session = Depends(get_db)):
    drink = Drinks(user_id=request.user_id, quantity=request.quantity)
    db.add(drink)
    db.commit()
    db.refresh(drink)
    logger.info(f"Drink added: {request.quantity:.1f}ml for user_id={request.user_id} (drink_id={drink.id})")
    _write_latest_drinks(db)
    return drink

@app.post("/addDrinkToActiveUser")
async def add_drink_to_active(request:DrinkQuantitySchema, db: Session = Depends(get_db)):
    currentActive = db.query(User).filter(User.active == True).first()
    if not currentActive:
        logger.warning("addDrinkToActiveUser called but no user is currently active")
        raise HTTPException(status_code=400, detail="No active user")
    drink = Drinks(user_id=currentActive.id, quantity=request.quantity)
    db.add(drink)
    db.commit()
    db.refresh(drink)
    logger.info(f"Drink added: {request.quantity:.1f}ml for '{currentActive.name}' (user_id={currentActive.id}, drink_id={drink.id})")
    _write_latest_drinks(db)
    return drink


### Keg management endpoints

@app.get("/kegs", response_model=List[KegResponse])
async def get_kegs(db: Session = Depends(get_db)):
    return db.query(Keg).all()

@app.post("/keg", response_model=KegResponse)
async def create_keg(request: KegSchema, db: Session = Depends(get_db)):
    keg = Keg(
        name=request.name,
        keg_size=request.keg_size,
        density=request.density,
        image_url=request.image_url,
        active=False,
    )
    db.add(keg)
    db.commit()
    db.refresh(keg)
    logger.info(f"Keg created: '{keg.name}' {keg.keg_size}L (ID={keg.id})")
    return keg

@app.patch("/keg/{id}", response_model=KegResponse)
async def update_keg(id: int, request: KegUpdateSchema, db: Session = Depends(get_db)):
    keg = db.get(Keg, id)
    if not keg:
        raise HTTPException(status_code=404, detail="Keg not found")
    if request.name is not None:
        keg.name = request.name
    if request.keg_size is not None:
        keg.keg_size = request.keg_size
    if request.density is not None:
        keg.density = request.density
    if request.image_url is not None:
        keg.image_url = request.image_url
    db.commit()
    db.refresh(keg)
    logger.info(f"Keg updated: ID={id}")
    return keg

@app.delete("/keg/{id}", status_code=204)
async def delete_keg(id: int, db: Session = Depends(get_db)):
    keg = db.get(Keg, id)
    if not keg:
        raise HTTPException(status_code=404, detail="Keg not found")
    db.delete(keg)
    db.commit()
    logger.info(f"Keg deleted: ID={id}")

@app.post("/keg/{id}/activate", response_model=KegResponse)
async def activate_keg(id: int, db: Session = Depends(get_db)):
    keg = db.get(Keg, id)
    if not keg:
        raise HTTPException(status_code=404, detail="Keg not found")
    # Deactivate all kegs then activate the requested one
    db.query(Keg).update({Keg.active: False})
    keg.active = True
    db.commit()
    db.refresh(keg)
    logger.info(f"Keg activated: '{keg.name}' (ID={id})")
    return keg


import redis
import json

# Redis configuration
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
r = redis.from_url(redis_url)

def _write_app_state():
    """Publish asyncState to Redis so the worker can read the current mode."""
    try:
        r.set('app_state', asyncState.model_dump_json())
    except Exception as e:
        logger.warning(f"Could not write app state to Redis: {e}")

def _write_latest_drinks(db: Session):
    """Write the 5 most recent drinks (with user name) to Redis for the WebSocket tick."""
    try:
        rows = db.query(Drinks).options(selectinload(Drinks.user)).order_by(Drinks.timestamp.desc()).limit(5).all()
        data = [
            {
                "user_name": d.user.name if d.user else None,
                "quantity": d.quantity,
                "timestamp": d.timestamp.isoformat() if d.timestamp else None,
            }
            for d in rows
        ]
        r.set('latest_drinks', json.dumps(data))
    except Exception as e:
        logger.warning(f"Could not write latest drinks to Redis: {e}")

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
    keg_refresh_ticks = 0
    cached_keg_info: Optional[KegInfo] = None
    cached_remaining_l: Optional[float] = None

    while True:
        try:
            # Sync local state from Redis so worker-driven transitions
            # (e.g. CAPTURE -> DETECT after N images) reach the frontend
            state_data = r.get('app_state')
            if state_data:
                state = json.loads(state_data)
                async_state.app_mode = AppModes(state['app_mode'])
                async_state.saved_images = state['saved_images']
                async_state.user_id = state['user_id']

            latest_drinks: List[LatestDrink] = []
            latest_drinks_data = r.get('latest_drinks')
            if latest_drinks_data:
                latest_drinks = [LatestDrink(**d) for d in json.loads(latest_drinks_data)]

            current_pour: float = 0.0
            current_pour_data = r.get('current_pour')
            if current_pour_data:
                try:
                    current_pour = float(current_pour_data)
                except (ValueError, TypeError):
                    pass

            # Refresh keg info and remaining beer every ~5 seconds (50 ticks × 100ms)
            keg_refresh_ticks += 1
            if keg_refresh_ticks >= 50:
                keg_refresh_ticks = 0
                remaining_raw = r.get('remaining_beer_kg')
                db = SessionLocal()
                try:
                    active_keg = db.query(Keg).filter(Keg.active == True).first()
                    if active_keg:
                        density = active_keg.density if active_keg.density else 1.0
                        cached_keg_info = KegInfo(
                            keg_size=active_keg.keg_size,
                            name=active_keg.name,
                            image_url=active_keg.image_url,
                        )
                        if remaining_raw is not None:
                            try:
                                remaining_kg = float(remaining_raw)
                                cached_remaining_l = remaining_kg / density
                            except (ValueError, TypeError):
                                cached_remaining_l = None
                    else:
                        cached_keg_info = None
                        cached_remaining_l = None
                finally:
                    db.close()

            last_results = r.get('last_face_locations')
            if last_results:
                results = json.loads(last_results)
                faces_output = Faces(
                    faces=results.get('face_locations', []),
                    app_state=async_state,
                    detected_face=results.get('user_ids', []),
                    latest_drinks=latest_drinks,
                    current_pour=current_pour,
                    remaining_beer_l=cached_remaining_l,
                    active_keg=cached_keg_info,
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
    _write_app_state()
    return asyncState

@app.post("/detectFace")
async def detect_face():
    """
    This function toggles the app behavior, so it starts capturing data
    """
    asyncState.app_mode = AppModes.DETECT
    asyncState.saved_images = 0
    asyncState.user_id = 0
    _write_app_state()
    return asyncState

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/", StaticFiles(directory=static_dir), name="static")