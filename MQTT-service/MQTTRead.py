import paho.mqtt.client as mqtt # type: ignore
import requests
import secrets
import datetime
from threading import Timer

TargetTopic = secrets.MQTT_info['target_topic']
USERNAME = secrets.MQTT_info['username']
PASSWORD = secrets.MQTT_info['password']
api_url = secrets.MQTT_info['api_url']

def register_drink(value):
    print(value)
    response = requests.post(url=api_url,json={"quantity":value})
    print(f"{datetime.datetime.now()} - Message sent to add {value}")
    print(response)

def delay_register(value):
    global myTimer
    myTimer = Timer(10,register_drink,[value])
delay_register(0)

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
    drink_quantity = msg.payload.decode()
    print(drink_quantity)
    delay_register(float(drink_quantity)*1000)
    myTimer.start()


mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqttc.username_pw_set(USERNAME,PASSWORD)
mqttc.on_connect = on_connect
mqttc.on_message = on_message

mqttc.connect(secrets.MQTT_info['mqtt_server'], 1883, 60)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
mqttc.loop_forever()