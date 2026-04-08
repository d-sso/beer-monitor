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

# Initialize face recognition controller
fr_controller = face_recognition_controller(logger)

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

def process_frames():
    logger.info("Worker started, waiting for frames...")
    while True:
        try:
            # Pop a frame from the queue
            _, data = r.brpop('frame_queue')

            # Decode image
            nparr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is not None:
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

        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    process_frames()
