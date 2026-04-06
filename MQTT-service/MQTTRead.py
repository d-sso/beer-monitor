import paho.mqtt.client as mqtt # type: ignore
import requests
import datetime
import os
from threading import Timer

try:
    import local_secrets
    secrets = local_secrets.MQTT_info
except ImportError:
    secrets = {}

TargetTopic = os.environ.get('MQTT_TARGET_TOPIC', secrets.get('target_topic', 'beer/quantity'))
USERNAME = os.environ.get('MQTT_USERNAME', secrets.get('username', ''))
PASSWORD = os.environ.get('MQTT_PASSWORD', secrets.get('password', ''))
api_url = os.environ.get('API_URL', secrets.get('api_url', 'http://api/drinks'))
mqtt_server = os.environ.get('MQTT_SERVER', secrets.get('mqtt_server', 'localhost'))
mqtt_port = int(os.environ.get('MQTT_PORT', secrets.get('mqtt_port', 1883)))

def register_drink(value):
    print(value)
    try:
        response = requests.post(url=api_url,json={"quantity":value},verify=False)
        print(f"{datetime.datetime.now()} - Message sent to add {value}")
        print(response)
    except Exception as e:
        print(f"{datetime.datetime.now()} - Error sending message to API: {e}")

def delay_register(value):
    global myTimer
    myTimer = Timer(10,register_drink,[value])

# Initialize myTimer to avoid NameError
myTimer = Timer(10, register_drink, [0])

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"{datetime.datetime.now()} - Connected with result code {reason_code}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(TargetTopic)

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    try:
        print(f"{datetime.datetime.now()} - " + msg.topic+" "+str(msg.payload.decode()))
    except:
        print(f"{datetime.datetime.now()} - " + msg.topic + " can't decode")

    myTimer.cancel()
    try:
        drink_quantity = msg.payload.decode()
        print(drink_quantity)
        delay_register(float(drink_quantity)*1000)
        myTimer.start()
    except Exception as e:
        print(f"{datetime.datetime.now()} - Error processing message: {e}")


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