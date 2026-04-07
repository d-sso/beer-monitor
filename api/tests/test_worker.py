import pytest
from unittest.mock import patch, MagicMock, ANY
import numpy as np
import cv2
import json
from app.worker import process_frames, set_active_user
from app.models import User

@patch("app.worker.SessionLocal")
def test_set_active_user(mock_session_local):
    """
    Tests the activation of a user, ensuring that when one user is activated,
    the previously active user is deactivated.
    """
    # Setup mocks
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    # Mock users
    active_user = User(id=1, name="Active", active=True)
    target_user = User(id=2, name="Target", active=False)

    # Mock queries
    def mock_query(model):
        q = MagicMock()
        if model == User:
            # For get(2)
            q.get.return_value = target_user
            # For filter(User.active == True).first()
            q.filter.return_value.first.return_value = active_user
        return q

    mock_db.query.side_effect = mock_query

    # Execute
    set_active_user(2)

    # Verify
    assert active_user.active == False
    assert target_user.active == True
    mock_db.commit.assert_called_once()

@patch("app.worker.r")
@patch("app.worker.fr_controller")
@patch("app.worker.set_active_user")
def test_process_frames_recognizes_user(mock_set_active, mock_fr, mock_redis):
    """
    Tests that the worker correctly processes an image frame, identifies a user,
    and triggers their activation.
    """
    # Build a valid JPEG image so cv2.imdecode returns a real array
    blank = np.zeros((64, 64, 3), dtype=np.uint8)
    _, encoded = cv2.imencode('.jpg', blank)
    img_bytes = encoded.tobytes()

    # First call returns a valid frame; second raises SystemExit to break the
    # infinite loop. SystemExit is not caught by `except Exception`, so it
    # propagates cleanly out of process_frames().
    mock_redis.brpop.side_effect = [
        ("frame_queue", img_bytes),
        SystemExit(0),
    ]

    # Mock face recognition to return a known user ID and confidence score
    mock_fr.recognize_faces.return_value = {
        "user_ids": [123],
        "face_locations": [[10, 10, 50, 50]],
        "confidence_scores": [85.0],
    }

    with pytest.raises(SystemExit):
        process_frames()

    # Verify recognition was called and the user was activated
    mock_fr.recognize_faces.assert_called_once()
    mock_set_active.assert_called_once_with(123)
    # Verify face locations were stored in Redis
    mock_redis.set.assert_any_call('last_face_locations', ANY)
