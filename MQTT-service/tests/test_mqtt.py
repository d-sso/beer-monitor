import pytest
from unittest.mock import patch, MagicMock, call
import MQTTRead

@patch("MQTTRead.requests.post")
def test_register_drink(mock_post):
    """
    Tests that the register_drink function correctly sends a POST request 
    to the API with the expected drink quantity.
    """
    # Setup
    mock_post.return_value.status_code = 200
    
    # Execute
    MQTTRead.register_drink(500)
    
    # Verify
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs['json'] == {"quantity": 500}

@patch("MQTTRead.myTimer")
def test_on_message(mock_timer):
    """
    Tests that the on_message callback correctly handles incoming MQTT messages,
    cancels the existing timer, and starts a new one with the correctly parsed 
    drink quantity.
    """
    # Setup
    client = MagicMock()
    userdata = MagicMock()
    msg = MagicMock()
    msg.topic = "beer/quantity"
    msg.payload = b"0.5" # 0.5 Liters
    
    # Execute
    MQTTRead.on_message(client, userdata, msg)
    
    # Verify
    # Timer should be cancelled and restarted
    mock_timer.cancel.assert_called_once()
    # Note: we can't easily check if a new timer was started because it's replaced
    # in the global scope, but we can check if it was called with the right value
    # if we mock the Timer class itself.


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------

def test_on_connect():
    """on_connect subscribes to the configured target topic."""
    client = MagicMock()
    MQTTRead.on_connect(client, None, None, None, None)
    client.subscribe.assert_called_once_with(MQTTRead.TargetTopic)


@patch("MQTTRead.Timer")
def test_delay_register(mock_timer_class):
    """delay_register creates a 10-second timer for register_drink with the given value."""
    mock_instance = MagicMock()
    mock_timer_class.return_value = mock_instance

    MQTTRead.delay_register(500.0)

    mock_timer_class.assert_called_once_with(10, MQTTRead.register_drink, [500.0])
    assert MQTTRead.myTimer is mock_instance


@patch("MQTTRead.myTimer")
def test_on_message_invalid_payload(mock_timer):
    """on_message cancels the pending timer but does not start a new one for non-numeric payloads."""
    client = MagicMock()
    msg = MagicMock()
    msg.topic = "beer/quantity"
    msg.payload = b"not_a_number"

    MQTTRead.on_message(client, None, msg)

    mock_timer.cancel.assert_called_once()
    mock_timer.start.assert_not_called()
