import os
import time
import json
import redis
import cv2
import numpy as np
import logging
from app.face_recognition_control import face_recognition_controller
from app.database import SessionLocal, engine
from app.models import Base, User

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")

# Redis configuration
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
r = redis.from_url(redis_url)

# Ensure tables exist (in case the worker starts before the API)
Base.metadata.create_all(bind=engine)

# App mode constants (match AppModes enum in main.py)
APP_MODE_CAPTURE = 1
APP_MODE_DETECT = 2

# Initialize face recognition controller
fr_controller = face_recognition_controller(logger)

def _get_app_state():
    raw = r.get('app_state')
    if raw:
        return json.loads(raw)
    return {'app_mode': APP_MODE_DETECT, 'user_id': 0, 'n_images': 10, 'saved_images': 0}

def _set_app_state(state):
    r.set('app_state', json.dumps(state))

def set_active_user(user_id):
    db = SessionLocal()
    try:
        user = db.query(User).get(int(user_id))
        if user and not user.active:
            current_active = db.query(User).filter(User.active == True).first()
            if current_active:
                current_active.active = False
            user.active = True
            db.commit()
            logger.info(f"Activated user: {user.name} (ID: {user_id})")
    except Exception as e:
        logger.error(f"Error activating user {user_id}: {e}")
    finally:
        db.close()

def _handle_capture(img, state):
    user_id = state.get('user_id', 0)
    n_images = state.get('n_images', 10)
    saved_images = state.get('saved_images', 0)

    result = fr_controller.encode_new_image(str(user_id), img)

    if result == 1:
        saved_images += 1
        state['saved_images'] = saved_images
        logger.info(f"Captured encoding {saved_images}/{n_images} for user_id={user_id}")
        if saved_images >= n_images:
            state['app_mode'] = APP_MODE_DETECT
            state['saved_images'] = 0
            logger.info(f"Finished capturing {n_images} encodings for user_id={user_id}, switching to DETECT mode")
        _set_app_state(state)
    elif result == 0:
        logger.debug(f"No face detected in capture frame for user_id={user_id}, skipping")
    else:
        logger.warning(f"Multiple faces in capture frame for user_id={user_id}, skipping")

    # Push a heartbeat result so the detect loop keeps sending app_state to the frontend
    r.set('last_face_locations', json.dumps({'face_locations': [], 'user_ids': [], 'confidence_scores': []}))
    r.expire('last_face_locations', 2)

def _handle_detect(img):
    results = fr_controller.recognize_faces(img)
    user_ids = results.get('user_ids', [])
    confidence_scores = results.get('confidence_scores', [])

    if not user_ids:
        logger.debug("No faces detected in frame")
    else:
        for uid, conf in zip(user_ids, confidence_scores):
            if uid == 0:
                logger.info("Face detected but not recognized (unknown)")
            else:
                conf_str = f"{conf:.1f}%" if conf is not None else "N/A"
                logger.info(f"Face recognized: user_id={uid}, confidence={conf_str}")

        known_users = [uid for uid in user_ids if uid != 0]
        if len(known_users) == 1:
            set_active_user(known_users[0])
            r.set('last_detected_user', json.dumps(results))
            r.expire('last_detected_user', 5)
        elif len(known_users) > 1:
            logger.warning(f"Multiple known users detected in one frame ({known_users}), skipping activation")

    r.set('last_face_locations', json.dumps(results))
    r.expire('last_face_locations', 2)

def process_frames():
    logger.info("Worker started, waiting for frames...")
    while True:
        try:
            _, data = r.brpop('frame_queue')

            nparr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                logger.debug("Could not decode frame, skipping")
                continue

            state = _get_app_state()
            if state.get('app_mode') == APP_MODE_CAPTURE:
                _handle_capture(img, state)
            else:
                _handle_detect(img)

        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    process_frames()
