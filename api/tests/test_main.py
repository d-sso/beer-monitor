import pytest
from unittest.mock import patch, MagicMock

def test_add_user(client):
    """
    Tests creating a new user and verifying its details.
    """
    response = client.post(
        "/adduser",
        json={"name": "Test User", "email": "test@example.com", "nickname": "Tester"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test User"
    assert data["nickname"] == "Tester"

def test_get_users(client):
    """
    Tests fetching a list of all users.
    """
    client.post("/adduser", json={"name": "User 1", "email": "1@ex.com", "nickname": "u1"})
    client.post("/adduser", json={"name": "User 2", "email": "2@ex.com", "nickname": "u2"})
    
    response = client.get("/users")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "User 1"
    assert data[1]["name"] == "User 2"

def test_set_active_user(client):
    """
    Tests setting a user as 'active' and ensuring only one user is active at a time.
    """
    # Create two users
    u1 = client.post("/adduser", json={"name": "U1", "email": "1@ex.com", "nickname": "u1"}).json()
    u2 = client.post("/adduser", json={"name": "U2", "email": "2@ex.com", "nickname": "u2"}).json()
    
    # Set U1 as active
    response = client.put(f"/user/active/{u1['id']}")
    assert response.status_code == 200
    assert response.json()["active"] == True
    
    # Set U2 as active
    response = client.put(f"/user/active/{u2['id']}")
    assert response.status_code == 200
    assert response.json()["active"] == True
    
    # Verify U1 is no longer active
    response = client.get("/users")
    users = response.json()
    u1_now = next(u for u in users if u["id"] == u1["id"])
    assert u1_now["active"] == False

def test_add_drink_to_active_user(client):
    """
    Tests registering a drink and assigning it to the currently active user.
    """
    # Create and activate a user
    user = client.post("/adduser", json={"name": "Drinker", "email": "d@ex.com", "nickname": "d"}).json()
    client.put(f"/user/active/{user['id']}")
    
    # Add a drink
    response = client.post("/addDrinkToActiveUser", json={"quantity": 500.0})
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user["id"]
    assert data["quantity"] == 500.0
    
    # Check user's total drinks
    response = client.get("/users")
    users = response.json()
    drinker = next(u for u in users if u["id"] == user["id"])
    assert len(drinker["drinks"]) == 1
    assert drinker["drinks"][0]["quantity"] == 500.0
