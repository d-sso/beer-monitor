import pytest
from unittest.mock import patch, MagicMock, ANY
import numpy as np
import cv2
import json
from app.worker import process_frames, set_active_user, APP_MODE_DETECT, APP_MODE_CAPTURE
from app.models import User


@pytest.fixture
def blank_jpeg():
    """Returns bytes for a minimal valid JPEG so cv2.imdecode succeeds."""
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    _, encoded = cv2.imencode('.jpg', img)
    return encoded.tobytes()


@pytest.fixture
def detect_state():
    """Returns a JSON-encoded default DETECT-mode app_state for mocking r.get."""
    return json.dumps({'app_mode': APP_MODE_DETECT, 'user_id': 0, 'n_images': 10, 'saved_images': 0})

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
def test_process_frames_recognizes_user(mock_set_active, mock_fr, mock_redis, blank_jpeg, detect_state):
    """
    Tests that the worker correctly processes an image frame, identifies a user,
    and triggers their activation.
    """
    mock_redis.brpop.side_effect = [("frame_queue", blank_jpeg), SystemExit(0)]
    mock_redis.get.return_value = detect_state
    mock_fr.recognize_faces.return_value = {
        "user_ids": [123],
        "face_locations": [[10, 10, 50, 50]],
        "confidence_scores": [85.0],
    }

    with pytest.raises(SystemExit):
        process_frames()

    mock_fr.recognize_faces.assert_called_once()
    mock_set_active.assert_called_once_with(123)
    mock_redis.set.assert_any_call('last_face_locations', ANY)


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------

@patch("app.worker.SessionLocal")
def test_set_active_user_already_active(mock_session_local):
    """set_active_user does nothing when the target user is already active."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_db.query.return_value.get.return_value = User(id=1, name="Same", active=True)

    set_active_user(1)

    mock_db.commit.assert_not_called()


@patch("app.worker.SessionLocal")
def test_set_active_user_not_found(mock_session_local):
    """set_active_user does nothing when the user ID does not exist."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_db.query.return_value.get.return_value = None

    set_active_user(999)

    mock_db.commit.assert_not_called()


@patch("app.worker.r")
@patch("app.worker.fr_controller")
@patch("app.worker.set_active_user")
def test_process_frames_unknown_face(mock_set_active, mock_fr, mock_redis, blank_jpeg, detect_state):
    """Worker does not activate anyone when the detected face is unrecognized."""
    mock_redis.brpop.side_effect = [("frame_queue", blank_jpeg), SystemExit(0)]
    mock_redis.get.return_value = detect_state
    mock_fr.recognize_faces.return_value = {
        "user_ids": [0],
        "face_locations": [[10, 10, 50, 50]],
        "confidence_scores": [None],
    }

    with pytest.raises(SystemExit):
        process_frames()

    mock_set_active.assert_not_called()


@patch("app.worker.r")
@patch("app.worker.fr_controller")
@patch("app.worker.set_active_user")
def test_process_frames_multiple_known_users(mock_set_active, mock_fr, mock_redis, blank_jpeg, detect_state):
    """Worker skips activation when multiple known users appear in one frame."""
    mock_redis.brpop.side_effect = [("frame_queue", blank_jpeg), SystemExit(0)]
    mock_redis.get.return_value = detect_state
    mock_fr.recognize_faces.return_value = {
        "user_ids": [1, 2],
        "face_locations": [[10, 10, 50, 50], [60, 60, 100, 100]],
        "confidence_scores": [90.0, 85.0],
    }

    with pytest.raises(SystemExit):
        process_frames()

    mock_set_active.assert_not_called()


@patch("app.worker.r")
@patch("app.worker.fr_controller")
@patch("app.worker.set_active_user")
def test_process_frames_invalid_image(mock_set_active, mock_fr, mock_redis):
    """Worker skips recognition when the frame cannot be decoded."""
    mock_redis.brpop.side_effect = [("frame_queue", b"not_an_image"), SystemExit(0)]

    with pytest.raises(SystemExit):
        process_frames()

    mock_fr.recognize_faces.assert_not_called()
    mock_set_active.assert_not_called()


@patch("app.worker.r")
@patch("app.worker.fr_controller")
@patch("app.worker.set_active_user")
def test_process_frames_capture_mode(mock_set_active, mock_fr, mock_redis, blank_jpeg):
    """Worker calls encode_new_image in CAPTURE mode and increments saved_images."""
    capture_state = json.dumps({'app_mode': APP_MODE_CAPTURE, 'user_id': 5, 'n_images': 10, 'saved_images': 3})
    mock_redis.brpop.side_effect = [("frame_queue", blank_jpeg), SystemExit(0)]
    mock_redis.get.return_value = capture_state
    mock_fr.encode_new_image.return_value = 1  # successful encoding

    with pytest.raises(SystemExit):
        process_frames()

    mock_fr.encode_new_image.assert_called_once_with('5', ANY)
    mock_fr.recognize_faces.assert_not_called()
    mock_set_active.assert_not_called()
    # State should be written back with saved_images=4
    written = json.loads(mock_redis.set.call_args_list[0][0][1])
    assert written['saved_images'] == 4
    assert written['app_mode'] == APP_MODE_CAPTURE  # not done yet (4 < 10)


@patch("app.worker.r")
@patch("app.worker.fr_controller")
@patch("app.worker.set_active_user")
def test_process_frames_capture_completes(mock_set_active, mock_fr, mock_redis, blank_jpeg):
    """Worker switches to DETECT mode after reaching n_images encodings."""
    capture_state = json.dumps({'app_mode': APP_MODE_CAPTURE, 'user_id': 5, 'n_images': 10, 'saved_images': 9})
    mock_redis.brpop.side_effect = [("frame_queue", blank_jpeg), SystemExit(0)]
    mock_redis.get.return_value = capture_state
    mock_fr.encode_new_image.return_value = 1

    with pytest.raises(SystemExit):
        process_frames()

    written = json.loads(mock_redis.set.call_args_list[0][0][1])
    assert written['saved_images'] == 0
    assert written['app_mode'] == APP_MODE_DETECT
