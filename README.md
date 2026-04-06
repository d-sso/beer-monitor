# Beer Monitor

Beer Monitor is a web application designed to track beer consumption in real-time, featuring automated user activation via facial recognition and integration with Home Assistant.

## Features

- **Real-time Consumption Tracking:** Monitors beer flow using load cells or flow meters integrated with Home Assistant.
- **Facial Recognition:** Automatically identifies and "activates" users via a camera feed, assigning subsequent beer consumption to the recognized individual.
- **Leaderboard:** Displays a ranking of users based on their total beer consumption.
- **MQTT Integration:** Seamlessly connects to Home Assistant via MQTT to receive sensor data.
- **Dockerized Architecture:** Easy deployment using Docker Compose.

## Architecture

The project consists of three main components:

1.  **Backend API (FastAPI):**
    - Handles user management and consumption data.
    - Manages the SQLite database (`beer.db`).
    - Provides a WebSocket endpoint for real-time facial recognition.
    - Implements face detection and recognition using the `face_recognition` library.

2.  **MQTT Service (Python):**
    - Listens to MQTT topics from Home Assistant.
    - Processes incoming data (e.g., weight changes from a load cell).
    - Communicates with the Backend API to register drinks.

3.  **Frontend (Angular):**
    - Provides a user-friendly interface for viewing rankings.
    - Captures camera feed and sends frames to the Backend API for facial recognition.

## Getting Started

### Prerequisites

- Docker and Docker Compose
- MQTT Broker (e.g., Mosquitto, often available via Home Assistant)

### Configuration

1.  **MQTT Service:** Configure your MQTT credentials and API URL. (Note: Secret handling is currently being improved to use environment variables).
2.  **API:** Ensure any necessary certificates for HTTPS/WSS are placed in the `api/certificate` directory (if applicable).

### Deployment

To start the entire stack, run:

```bash
docker-compose up --build
```

The services will be available at:
- **Frontend:** `http://localhost:8080`
- **Backend API:** `http://localhost:8000`

## Development

- **API:** Located in the `api` folder. Requirements are in `api/requirements.txt`.
- **MQTT Service:** Located in the `MQTT-service` folder.
- **Frontend:** Located in the `frontend` folder. Uses Angular CLI.
