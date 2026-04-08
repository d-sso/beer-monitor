import paho.mqtt.client as mqtt # type: ignore
import requests
import os
import logging
from threading import Timer
import redis

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mqtt-service")

try:
    import local_secrets
    secrets = local_secrets.MQTT_info
except ImportError:
    secrets = {}

TargetTopic = os.environ.get('MQTT_TARGET_TOPIC', secrets.get('target_topic', 'beer/quantity'))
TotalWeightTopic = os.environ.get('MQTT_TOTAL_WEIGHT_TOPIC', secrets.get('total_weight_topic', 'beer/total_weight'))
TareWeightTopic = os.environ.get('MQTT_TARE_WEIGHT_TOPIC', secrets.get('tare_weight_topic', 'beer/tare_weight'))
USERNAME = os.environ.get('MQTT_USERNAME', secrets.get('username', ''))
PASSWORD = os.environ.get('MQTT_PASSWORD', secrets.get('password', ''))
api_url = os.environ.get('API_URL', secrets.get('api_url', 'http://api/drinks'))
mqtt_server = os.environ.get('MQTT_SERVER', secrets.get('mqtt_server', 'localhost'))
mqtt_port = int(os.environ.get('MQTT_PORT', secrets.get('mqtt_port', 1883)))
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

r = redis.from_url(redis_url)

# In-memory cache for weight readings
_weight_state = {'total_kg': None, 'tare_kg': None}

def _write_current_pour(value_ml: float):
    """Write the current in-progress pour value (ml) to Redis."""
    try:
        r.set('current_pour', value_ml)
    except Exception as e:
        logger.warning(f"Could not write current_pour to Redis: {e}")

def _reset_current_pour():
    """Reset the pour gauge to 0 after a drink is committed."""
    try:
        r.set('current_pour', 0)
    except Exception as e:
        logger.warning(f"Could not reset current_pour in Redis: {e}")

def _update_remaining_beer():
    """Recalculate and write remaining_beer_kg to Redis when both weights are known."""
    total = _weight_state['total_kg']
    tare = _weight_state['tare_kg']
    if total is None or tare is None:
        return
    remaining_kg = max(0.0, total - tare)
    try:
        r.set('remaining_beer_kg', remaining_kg)
        logger.debug(f"Remaining beer: {remaining_kg:.3f} kg (total={total}, tare={tare})")
    except Exception as e:
        logger.warning(f"Could not write remaining_beer_kg to Redis: {e}")

def register_drink(value):
    logger.info(f"Registering drink: {value:.1f}ml -> POST {api_url}")
    try:
        response = requests.post(url=api_url, json={"quantity": value}, verify=False)
        logger.info(f"Drink registration response: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to register drink ({value:.1f}ml): {e}")
    finally:
        _reset_current_pour()

def delay_register(value):
    global myTimer
    myTimer = Timer(10, register_drink, [value])
    logger.info(f"Drink detected: {value:.1f}ml — will register in 10s")

# Initialize myTimer to avoid NameError
myTimer = Timer(10, register_drink, [0])

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    logger.info(f"Connected to MQTT broker {mqtt_server}:{mqtt_port} (reason: {reason_code}), subscribing to topics")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(TargetTopic)
    client.subscribe(TotalWeightTopic)
    client.subscribe(TareWeightTopic)

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    try:
        raw_value = msg.payload.decode()
        logger.info(f"MQTT message received: topic='{msg.topic}', raw_value='{raw_value}'")
    except Exception:
        logger.warning(f"MQTT message received on '{msg.topic}' but payload could not be decoded")
        return

    # Handle weight topics for remaining beer display
    if msg.topic == TotalWeightTopic:
        try:
            _weight_state['total_kg'] = float(raw_value)
            _update_remaining_beer()
        except Exception as e:
            logger.error(f"Error processing total_weight (value='{raw_value}'): {e}")
        return

    if msg.topic == TareWeightTopic:
        try:
            _weight_state['tare_kg'] = float(raw_value)
            _update_remaining_beer()
        except Exception as e:
            logger.error(f"Error processing tare_weight (value='{raw_value}'): {e}")
        return

    # Handle pour quantity topic
    myTimer.cancel()
    try:
        quantity_ml = float(raw_value) * 1000
        _write_current_pour(quantity_ml)
        delay_register(quantity_ml)
        myTimer.start()
    except Exception as e:
        logger.error(f"Error processing MQTT message (topic='{msg.topic}', value='{raw_value}'): {e}")


def main():
    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if USERNAME and PASSWORD:
        mqttc.username_pw_set(USERNAME,PASSWORD)
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message

    mqttc.connect(mqtt_server, mqtt_port, 60)

    # Blocking call that processes network traffic, dispatches callbacks and
    # handles reconnecting.
    # Other loop*() functions are available that give a threaded interface and a
    # manual interface.
    mqttc.loop_forever()

if __name__ == "__main__":
    main()
