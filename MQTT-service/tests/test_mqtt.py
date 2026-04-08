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
    """on_connect subscribes to all three configured topics."""
    client = MagicMock()
    MQTTRead.on_connect(client, None, None, None, None)
    subscribed = [c.args[0] for c in client.subscribe.call_args_list]
    assert MQTTRead.TargetTopic in subscribed
    assert MQTTRead.TotalWeightTopic in subscribed
    assert MQTTRead.TareWeightTopic in subscribed


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


# ---------------------------------------------------------------------------
# Issue #5: Real-time pour gauge — Redis writes
# ---------------------------------------------------------------------------

@patch("MQTTRead.myTimer")
@patch("MQTTRead.r")
def test_on_message_writes_current_pour_to_redis(mock_r, mock_timer):
    """on_message writes current_pour (ml) to Redis on each incoming value."""
    msg = MagicMock()
    msg.topic = "beer/quantity"
    msg.payload = b"0.5"  # 0.5 kg -> 500 ml

    MQTTRead.on_message(None, None, msg)

    mock_r.set.assert_called_with('current_pour', 500.0)


@patch("MQTTRead.requests.post")
@patch("MQTTRead.r")
def test_register_drink_resets_current_pour(mock_r, mock_post):
    """register_drink resets current_pour to 0 in Redis after committing the drink."""
    mock_post.return_value.status_code = 200

    MQTTRead.register_drink(500.0)

    mock_r.set.assert_called_with('current_pour', 0)


@patch("MQTTRead.requests.post")
@patch("MQTTRead.r")
def test_register_drink_resets_current_pour_even_on_error(mock_r, mock_post):
    """register_drink resets current_pour even when the HTTP POST fails."""
    mock_post.side_effect = Exception("connection refused")

    MQTTRead.register_drink(300.0)

    mock_r.set.assert_called_with('current_pour', 0)


# ---------------------------------------------------------------------------
# Issue #7: Remaining beer — weight topic subscriptions
# ---------------------------------------------------------------------------

def test_on_connect_subscribes_to_weight_topics():
    """on_connect subscribes to pour quantity, total weight, and tare weight topics."""
    client = MagicMock()
    MQTTRead.on_connect(client, None, None, None, None)

    subscribed = [call.args[0] for call in client.subscribe.call_args_list]
    assert MQTTRead.TargetTopic in subscribed
    assert MQTTRead.TotalWeightTopic in subscribed
    assert MQTTRead.TareWeightTopic in subscribed


@patch("MQTTRead.r")
def test_on_message_total_weight_updates_state(mock_r):
    """on_message on TotalWeightTopic updates _weight_state and writes remaining_beer_kg when both known."""
    MQTTRead._weight_state['total_kg'] = None
    MQTTRead._weight_state['tare_kg'] = 5.0  # tare already known

    msg = MagicMock()
    msg.topic = MQTTRead.TotalWeightTopic
    msg.payload = b"20.0"  # 20 kg total

    MQTTRead.on_message(None, None, msg)

    assert MQTTRead._weight_state['total_kg'] == 20.0
    mock_r.set.assert_called_with('remaining_beer_kg', 15.0)


@patch("MQTTRead.r")
def test_on_message_tare_weight_updates_state(mock_r):
    """on_message on TareWeightTopic updates _weight_state and writes remaining_beer_kg when both known."""
    MQTTRead._weight_state['total_kg'] = 18.0
    MQTTRead._weight_state['tare_kg'] = None

    msg = MagicMock()
    msg.topic = MQTTRead.TareWeightTopic
    msg.payload = b"4.5"

    MQTTRead.on_message(None, None, msg)

    assert MQTTRead._weight_state['tare_kg'] == 4.5
    mock_r.set.assert_called_with('remaining_beer_kg', pytest.approx(13.5))


@patch("MQTTRead.r")
def test_remaining_beer_clamped_to_zero(mock_r):
    """remaining_beer_kg is never negative (e.g. if tare > total)."""
    MQTTRead._weight_state['tare_kg'] = 10.0

    msg = MagicMock()
    msg.topic = MQTTRead.TotalWeightTopic
    msg.payload = b"8.0"  # total < tare (sensor noise)

    MQTTRead.on_message(None, None, msg)

    mock_r.set.assert_called_with('remaining_beer_kg', 0.0)


@patch("MQTTRead.myTimer")
def test_weight_topic_does_not_trigger_drink_timer(mock_timer):
    """Messages on weight topics do not start the drink registration timer."""
    MQTTRead._weight_state['total_kg'] = None

    with patch("MQTTRead.r"):
        msg = MagicMock()
        msg.topic = MQTTRead.TotalWeightTopic
        msg.payload = b"15.0"
        MQTTRead.on_message(None, None, msg)

    mock_timer.cancel.assert_not_called()
    mock_timer.start.assert_not_called()
