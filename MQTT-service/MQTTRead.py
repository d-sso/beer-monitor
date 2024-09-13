import paho.mqtt.client as mqtt # type: ignore
import requests
import secrets

TargetTopic = secrets.MQTT_info['target_topic']
USERNAME = secrets.MQTT_info['username']
PASSWORD = secrets.MQTT_info['password']
api_url = secrets.MQTT_info['api_url']

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected with result code {reason_code}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(TargetTopic)

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload.decode()))
    receivedValue = msg.payload.decode()
    response = requests.post(url=api_url,json={"quantity":receivedValue})
    print(response)


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