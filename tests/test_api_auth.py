# import pytest


# def test_register_user(client):
#     response = client.post(
#         "/auth/register",
#         json={
#             "email": "testuser@example.com",
#             "password": "testpassword",
#             "full_name": "Test User",
#             "role": "accountant"
#         }
#     )
#     assert response.status_code == 201
#     data = response.json()
#     assert data["email"] == "testuser@example.com"
#     assert "id" in data

# def test_login_user(client):
#     # 1. Ensure the user is registered first
#     email, password = "login@example.com", "testpassword123"
#     client.post("/auth/register", json={"email": email, "password": password})
    
#     # 2. Test login: OAuth2 token endpoints expect form data (data=), not JSON (json=)
#     response = client.post(
#         "/auth/token",
#         data={"username": email, "password": password}
#     )
#     assert response.status_code == 200
#     data = response.json()
#     assert "access_token" in data
#     assert data["token_type"] == "bearer"

# def test_read_users_me(client):
#     # 1. Setup: Register and Login to obtain a valid JWT token
#     email, password = "user1@example.com", "mypassword123"
#     # client.post("/auth/register", json={"email": email, "password": password})
#     login_res = client.post("/auth/token", data={"username": email, "password": password})
#     token = login_res.json()["access_token"]

#     # 2. Execute: Call the 'me' endpoint with the Bearer token in the headers
#     response = client.get(
#         "/auth/users/me",
#         headers={"Authorization": f"Bearer {token}"}
#     )
#     assert response.status_code == 200
#     data = response.json()
#     assert data["email"] == email