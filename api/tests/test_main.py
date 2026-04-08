import pytest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------

def test_add_user_already_exists(client):
    """Adding the same user twice returns the existing record without duplicating."""
    r1 = client.post("/adduser", json={"name": "Dup", "email": "d@ex.com", "nickname": "d"})
    r2 = client.post("/adduser", json={"name": "Dup", "email": "d@ex.com", "nickname": "d"})
    assert r2.status_code == 200
    assert r2.json()["id"] == r1.json()["id"]
    users = client.get("/users").json()
    assert len([u for u in users if u["name"] == "Dup"]) == 1


def test_get_active_user(client):
    """GET /user/active returns the currently active user."""
    user = client.post("/adduser", json={"name": "ActiveOne", "email": "a@ex.com", "nickname": "a"}).json()
    client.put(f"/user/active/{user['id']}")
    response = client.get("/user/active")
    assert response.status_code == 200
    assert response.json()["id"] == user["id"]


def test_get_active_user_when_none(client):
    """GET /user/active returns null when no user is active."""
    response = client.get("/user/active")
    assert response.status_code == 200
    assert response.json() is None


def test_get_user_by_name(client):
    """GET /user/{name} returns the correct user."""
    client.post("/adduser", json={"name": "ByName", "email": "n@ex.com", "nickname": "bn"})
    response = client.get("/user/ByName")
    assert response.status_code == 200
    assert response.json()["name"] == "ByName"


def test_get_drinks(client):
    """GET /drinks returns all recorded drinks."""
    user = client.post("/adduser", json={"name": "Drinker2", "email": "d2@ex.com", "nickname": "d2"}).json()
    client.put(f"/user/active/{user['id']}")
    client.post("/addDrinkToActiveUser", json={"quantity": 330.0})
    client.post("/addDrinkToActiveUser", json={"quantity": 500.0})
    response = client.get("/drinks")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_add_drink(client):
    """POST /addDrink assigns a drink directly to a specified user."""
    user = client.post("/adduser", json={"name": "DirectDrinker", "email": "dd@ex.com", "nickname": "dd"}).json()
    response = client.post("/addDrink", json={"user_id": user["id"], "quantity": 250.0})
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user["id"]
    assert data["quantity"] == 250.0


def test_add_drink_to_active_user_no_active(client):
    """POST /addDrinkToActiveUser returns 400 when no user is active."""
    response = client.post("/addDrinkToActiveUser", json={"quantity": 500.0})
    assert response.status_code == 400


def test_set_active_user_nonexistent(client):
    """PUT /user/active/{id} with an unknown ID returns null without error."""
    response = client.put("/user/active/99999")
    assert response.status_code == 200
    assert response.json() is None


def test_record_face(client):
    """POST /recordFace switches the app into CAPTURE mode."""
    response = client.post("/recordFace?id=1")
    assert response.status_code == 200
    assert response.json()["app_mode"] == 1  # AppModes.CAPTURE


def test_detect_face(client):
    """POST /detectFace switches the app back into DETECT mode."""
    response = client.post("/detectFace")
    assert response.status_code == 200
    assert response.json()["app_mode"] == 2  # AppModes.DETECT


# ---------------------------------------------------------------------------
# Issue #2: User management CRUD
# ---------------------------------------------------------------------------

def test_update_user_name(client):
    """PATCH /user/{id} updates the user's name."""
    user = client.post("/adduser", json={"name": "OldName", "email": "o@ex.com", "nickname": "old"}).json()
    response = client.patch(f"/user/{user['id']}", json={"name": "NewName"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "NewName"
    assert data["email"] == "o@ex.com"   # unchanged
    assert data["nickname"] == "old"      # unchanged


def test_update_user_email_and_nickname(client):
    """PATCH /user/{id} can update email and nickname independently."""
    user = client.post("/adduser", json={"name": "Sam", "email": "old@ex.com", "nickname": "s"}).json()
    response = client.patch(f"/user/{user['id']}", json={"email": "new@ex.com", "nickname": "sammy"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Sam"           # unchanged
    assert data["email"] == "new@ex.com"
    assert data["nickname"] == "sammy"


def test_update_user_not_found(client):
    """PATCH /user/{id} returns 404 for a non-existent user."""
    response = client.patch("/user/99999", json={"name": "Ghost"})
    assert response.status_code == 404


def test_delete_user(client):
    """DELETE /user/{id} removes the user; subsequent GET /users excludes them."""
    user = client.post("/adduser", json={"name": "ToDelete", "email": "d@ex.com", "nickname": "del"}).json()
    response = client.delete(f"/user/{user['id']}")
    assert response.status_code == 204

    users = client.get("/users").json()
    assert all(u["id"] != user["id"] for u in users)


def test_delete_user_not_found(client):
    """DELETE /user/{id} returns 404 for a non-existent user."""
    response = client.delete("/user/99999")
    assert response.status_code == 404


def test_delete_user_drinks_preserved(client):
    """Drinks belonging to a deleted user are kept (no cascade delete)."""
    user = client.post("/adduser", json={"name": "DrinkOwner", "email": "do@ex.com", "nickname": "do"}).json()
    client.put(f"/user/active/{user['id']}")
    client.post("/addDrinkToActiveUser", json={"quantity": 500.0})

    client.delete(f"/user/{user['id']}")

    drinks = client.get("/drinks").json()
    assert any(d["user_id"] == user["id"] for d in drinks)
