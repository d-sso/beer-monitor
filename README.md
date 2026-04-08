# Beer Monitor

Beer Monitor is a web application that tracks beer consumption in real-time, using facial recognition to identify who is drinking and Home Assistant MQTT sensors to measure how much.

## Features

- **Real-time consumption tracking:** Monitors beer flow via load cells or flow meters integrated with Home Assistant.
- **Facial recognition:** Automatically identifies users from a camera feed and activates them as the current drinker.
- **Leaderboard:** Ranks users by total beer consumption, updated in real-time.
- **MQTT integration:** Receives sensor data from Home Assistant via MQTT.
- **HTTPS/WSS:** Served over HTTPS so the browser camera API works when accessed from devices other than localhost.
- **Dockerized:** Full stack runs with a single `docker compose up`.

## Architecture

Five services defined in `docker-compose.yaml`:

| Service | Description |
|---|---|
| `api` | FastAPI backend — user management, drink registration, WebSocket for face detection frames |
| `face-recognition-worker` | Reads frames from Redis, runs face recognition/capture, writes results back to Redis |
| `frontend` | Angular app served by nginx over HTTPS |
| `mqtt-service` | Connects to the MQTT broker, translates sensor messages into drink registrations |
| `redis` | Message bus between the API and the worker (frame queue, app state, detection results) |

### User registration and face capture flow

1. A new user is added via the web UI (`POST /adduser`).
2. The API switches `app_state` in Redis to `CAPTURE` mode for that user.
3. The frontend shows a centering overlay and begins streaming camera frames via WebSocket.
4. The API pushes frames into the Redis `frame_queue`.
5. The worker detects the face in each frame and saves the encoding to the database, incrementing `saved_images` in Redis.
6. After 10 successful captures the worker switches `app_state` back to `DETECT` mode.
7. The frontend removes the overlay and returns to normal recognition.

### Drink registration flow

1. The MQTT service receives a sensor message (e.g. weight change in grams).
2. It waits 10 seconds for the value to stabilise, then calls `POST /drinks` on the API.
3. The API assigns the drink to whichever user is currently active.
4. The leaderboard updates automatically on the next frontend poll.

## Getting Started

### Prerequisites

- Docker and Docker Compose
- An MQTT broker reachable from the host (e.g. Mosquitto via Home Assistant)

### 1. SSL certificate

The app is served over HTTPS. A self-signed certificate is required and must be placed at:

```
api/certificate/cert.pem
api/certificate/key.pem
```

Generate one with `openssl` (replace `<YOUR_IP>` with the host's LAN IP if you want to access from other devices):

```bash
openssl req -x509 -newkey rsa:4096 \
  -keyout api/certificate/key.pem \
  -out api/certificate/cert.pem \
  -sha256 -days 365 -nodes \
  -subj "/CN=beer-monitor" \
  -addext "subjectAltName=IP:<YOUR_IP>,IP:127.0.0.1,DNS:localhost"
```

The `api/certificate/` directory is git-ignored — never commit certificates or private keys.

### 2. MQTT credentials

Copy `.env.example` to `.env` and fill in your broker details:

```bash
cp .env.example .env
```

```dotenv
MQTT_SERVER=homeassistant.local
MQTT_PORT=1883
MQTT_USERNAME=your_username
MQTT_PASSWORD=your_password
MQTT_TARGET_TOPIC=+/sensor/last_pour/state
```

`.env` is git-ignored and is loaded automatically by Docker Compose.

### 3. Start the stack

```bash
docker compose up --build
```

The services will be available at:

| Service | URL |
|---|---|
| Frontend | `https://localhost:8080` |
| Backend API | `https://localhost:8000` |

### Accessing from another device on the network

Because the app uses the browser camera API, it must be served over HTTPS when accessed from any address other than `localhost`. Make sure the certificate's SAN includes the host's LAN IP (see step 1 above), then navigate to `https://<HOST_IP>:8080`.

The browser will warn about the self-signed certificate. You also need to explicitly trust the API origin — open `https://<HOST_IP>:8000` in a tab and accept the warning there too, otherwise WebSocket and API calls from the frontend will be blocked.

## Development

### Running tests

**API and worker:**
```bash
docker run --rm \
  -v $(pwd)/api:/code \
  -e DATABASE_URL=sqlite:///./beer.db \
  -e REDIS_URL=redis://localhost:6379/0 \
  beer-monitor-api \
  python -m pytest /code/tests/ -v
```

**MQTT service:**
```bash
docker run --rm \
  -v $(pwd)/MQTT-service:/code \
  beer-monitor-mqtt-service \
  python -m pytest /code/tests/ -v
```

### Project layout

```
api/            FastAPI backend + face recognition worker
  app/          Application source
  tests/        Pytest test suite
  certificate/  SSL cert and key (git-ignored, generate locally)
  data/         Persistent data volume (database, face images)
MQTT-service/   MQTT listener
  tests/        Pytest test suite
frontend/       Angular application
```

### Key environment variables

| Variable | Service | Description |
|---|---|---|
| `DATABASE_URL` | api, worker | SQLite path — default `sqlite:////data/beer.db` |
| `REDIS_URL` | api, worker | Redis connection string |
| `IMAGES_PATH` | api, worker | Directory for saved face images |
| `MODEL_PATH` | api, worker | Directory for saved face encodings (legacy) |
| `MQTT_SERVER` | mqtt-service | Broker hostname |
| `MQTT_PORT` | mqtt-service | Broker port (default 1883) |
| `MQTT_USERNAME` | mqtt-service | Broker username |
| `MQTT_PASSWORD` | mqtt-service | Broker password |
| `MQTT_TARGET_TOPIC` | mqtt-service | Topic to subscribe to |
