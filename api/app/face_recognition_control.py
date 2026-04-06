import face_recognition
import cv2
import pickle
import os
from pathlib import Path
import app.util as util
import numpy as np
from app.database import SessionLocal
from app.models import User

def transform_coordinates(location):
    [top,right,bottom,left] = location
    return [left,bottom,(right-left),(top-bottom)]

class face_recognition_controller:
    
    model_file_path = os.environ.get('MODEL_PATH', 'saved_encodings')
    images_path = os.environ.get('IMAGES_PATH', 'imgs/')
    face_encodings = []
    user_ids = []
    buffer_images_to_save = None
    cascade_classifier = None
    logger = None

    ### TODO: how to pass logger to this class
    def __init__(self,logger):
        self.logger = logger
        self.load_model()
        self.buffer_images_to_save = list()
    
    def load_model(self):
        """
        Loads face encodings from the database.
        """
        try:
            db = SessionLocal()
            users = db.query(User).filter(User.face_encoding != None).all()
            self.face_encodings = []
            self.user_ids = []
            for user in users:
                # Deserialize from bytes to numpy array
                encoding = np.frombuffer(user.face_encoding, dtype=np.float64)
                self.face_encodings.append(encoding)
                self.user_ids.append(user.id)
            db.close()
            self.logger.info(f"Loaded {len(self.face_encodings)} face encodings from database.")
        except Exception as e:
            self.logger.error(f"Could not load model from database - {e}")

    def save_encoding_to_db(self, user_id, encoding):
        """
        Saves a single face encoding to the database for a specific user.
        """
        try:
            db = SessionLocal()
            user = db.query(User).get(int(user_id))
            if user:
                # Serialize numpy array to bytes
                user.face_encoding = encoding.tobytes()
                db.commit()
                self.logger.info(f"Saved face encoding for user {user.name} to database.")
            db.close()
        except Exception as e:
            self.logger.error(f"Could not save encoding to database for user {user_id} - {e}")

    def get_user_folder_path(self,user_id:str):
        """	
        This function creates a folder for the user if it does not exist and returns the path to the folder.	
        """	
        target_path = self.images_path + user_id
        # TODO: check if folder exists before throwing an error
        try:
            os.mkdir(target_path)
        except FileExistsError:
            self.logger.info(f"User folder for user id {user_id} already exists.")
        except PermissionError:
            self.logger.error(f"Permission error creating user folder for user id {user_id} with path {target_path}")
        except Exception as e:
            self.logger.error(f"Could not create user folder for user id {user_id} with path {target_path} - {e}")
        return target_path

    def encode_new_image(self, user_id:str, img):
        """
        This function encodes a new image, adds it to the list and buffer the image for saving later.
        Returns the number of faces detected in the image, if there are more than two faces detected, it will not add the encoding.
        If no face is detected, it will return 0.
        If an error occurrs, returns -1.
        """
        try:
            face_locations = face_recognition.face_locations(img)
            if len(face_locations) == 0:
                self.logger.error(f"No face detected in image")
                return 0
            if len(face_locations) > 1:
                self.logger.error(f"More than one face detected in image")
                return len(face_locations)
            face_encoding = face_recognition.face_encodings(img, face_locations)[0]
            
            # Save to database immediately
            self.save_encoding_to_db(user_id, face_encoding)
            
            # Update local lists
            self.face_encodings.append(face_encoding)
            self.user_ids.append(user_id)
            
            self.buffer_images_to_save.append(
                {
                    "user_id": user_id,
                    "img": img
                }
            )
            return 1
        except Exception as e:
            self.logger.error(f"Could not encode new image - {e}")
            return -1

    def save_images_on_buffer(self):
        """
        This function saves all the images on the buffer to the user's folder.
        """
        try:
            self.buffer_images_to_save.sort(key=lambda x: x["user_id"])
            curr_user_id = ''
            user_folder_path = ''
            for item in self.buffer_images_to_save:
                # iterate per item, if different user, change folder path. Might be a better way to do this.
                if item["user_id"] != curr_user_id:
                    curr_user_id = item["user_id"]
                    user_folder_path = self.get_user_folder_path(str(item["user_id"]))
                ### TODO currently will save incrementing the number of images in the folder, perhaps a good idea to overwrite them
                self.save_image(user_folder_path + "\\img" + str(len(os.listdir(user_folder_path))) + ".png", item["img"])
        except Exception as e:
            self.logger.error(f"Could not save buffered images - {e}")
        finally:
            self.buffer_images_to_save = list()

    def save_image(self,target_path:str, img):
        """
        This function saves an image to the target path.
        """
        try:
            cv2.imwrite(target_path, img)
            self.logger.info(f"New image saved at {target_path}")
        except Exception as e:
            self.logger.error(f"Could not save new image - {e}")
    
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

    def detect_faces(self, img):
        """
        This function detects faces in an image and returns the locations.
        """
        try:
            faces = face_recognition.face_locations(img)
            return faces
        except Exception as e:
            self.logger.error(f"Could not detect faces - {e}")
            return []
    
    def recognize_faces(self, img):
        """
        This function recognizes faces in an image and returns the user ids.

        Parameters:
        img (numpy.ndarray): The image in which to recognize faces.

        Returns:
        dict: A dictionary with two keys:
            - 'face_locations': A list of tuples representing the bounding boxes of the detected faces.
            - 'user_ids': A list of user IDs corresponding to the recognized faces.
        """
        try:
            face_locations = self.detect_faces(img)
            face_encodings = face_recognition.face_encodings(img, face_locations)
            user_ids = []
            for face_encoding in face_encodings:
                matches = face_recognition.compare_faces(self.face_encodings, face_encoding)
                user_id = 0
                if True in matches:
                    first_match_index = matches.index(True)
                    user_id = self.user_ids[first_match_index]
                user_ids.append(user_id)
            return {
                    "face_locations": [transform_coordinates(item) for item in face_locations],
                    "user_ids": user_ids
                }
        except Exception as e:
            self.logger.error(f"Could not recognize faces - {e}")
            return {}
    
    def train_model(self):
        """
        Legacy method updated to save to database.
        """
        try:
            folderPath = Path(self.images_path)
            if not folderPath.exists():
                return

            pathlist = [x for x in folderPath.iterdir() if x.is_dir()]

            for path in pathlist:
                userId = path.name
                if util.is_number(userId):
                    for file in path.glob('**/*.png'):
                        image = face_recognition.load_image_file(file)
                        face_encodings = face_recognition.face_encodings(image)
                        if len(face_encodings) > 0:
                            # We'll just take the first one found in the folder for now
                            self.save_encoding_to_db(userId, face_encodings[0])
                            break # Found one, move to next user
            
            # Reload from DB to refresh local state
            self.load_model()
        except Exception as e:
            self.logger.error(f"Could not train model - {e}")

