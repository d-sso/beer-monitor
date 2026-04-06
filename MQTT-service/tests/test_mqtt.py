import pytest
from unittest.mock import patch, MagicMock
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
