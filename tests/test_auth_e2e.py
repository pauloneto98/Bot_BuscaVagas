import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.api.server import app
from app.config import settings
from app.db.repositories import UserRepository, UserConfigRepository

client = TestClient(app)

def test_auth_and_user_creation_e2e():
    """Verify default admin login, new user creation by admin, login of new user, and role authorization."""
    # Ensure settings has authentication active during test
    original_disable_auth = settings.DISABLE_DASHBOARD_AUTH
    settings.DISABLE_DASHBOARD_AUTH = False

    test_email = "test_user_temp@example.com"
    test_password = "TemporaryPassword123"
    test_name = "User Test Temp"

    try:
        # 1. Test Login of the Default Admin User
        admin_email = settings.EMAIL_ADDRESS if settings.EMAIL_ADDRESS else "admin@admin.com"
        admin_password = settings.DASHBOARD_PASSWORD

        login_response = client.post("/api/login", json={
            "email": admin_email,
            "password": admin_password
        })
        
        assert login_response.status_code == 200, f"Admin login failed: {login_response.json()}"
        admin_data = login_response.json()
        assert "token" in admin_data
        admin_token = admin_data["token"]
        assert admin_data["user"]["email"] == admin_email
        assert admin_data["user"]["is_admin"] is True

        # 2. Test accessing /api/me with admin token
        me_response = client.get("/api/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert me_response.status_code == 200
        assert me_response.json()["email"] == admin_email

        # Clean up user if it already exists from previous failed run
        existing_user = UserRepository.get_by_email(test_email)
        if existing_user:
            UserRepository.delete(existing_user["id"])

        # 3. Create a new user using the admin token
        create_user_response = client.post("/api/admin/create-user", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": test_email,
                "password": test_password,
                "name": test_name,
                "is_admin": False
            }
        )
        assert create_user_response.status_code == 200, f"Failed to create user: {create_user_response.json()}"
        new_user_id = create_user_response.json()["user_id"]

        # Verify config exists
        user_config = UserConfigRepository.get_by_user_id(new_user_id)
        assert user_config is not None
        assert user_config["email_address"] == test_email

        # 4. Try creating user WITHOUT admin token (Should fail 401/403)
        unauthorized_create = client.post("/api/admin/create-user", 
            json={
                "email": "should_fail@example.com",
                "password": "Password123",
                "name": "Should Fail"
            }
        )
        assert unauthorized_create.status_code in (401, 403)

        # 5. Log in with the newly created user
        user_login_response = client.post("/api/login", json={
            "email": test_email,
            "password": test_password
        })
        assert user_login_response.status_code == 200
        user_data = user_login_response.json()
        user_token = user_data["token"]
        assert user_data["user"]["is_admin"] is False

        # 6. Verify new user can access /api/me but NOT create-user (403 Forbidden)
        user_me = client.get("/api/me", headers={"Authorization": f"Bearer {user_token}"})
        assert user_me.status_code == 200
        assert user_me.json()["email"] == test_email

        user_create_attempt = client.post("/api/admin/create-user", 
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "email": "regular_user_adding@example.com",
                "password": "Password123",
                "name": "Illegal Add"
            }
        )
        assert user_create_attempt.status_code == 403

        # 7. Test disabling user
        UserRepository.update_status(new_user_id, is_active=False)
        disabled_login = client.post("/api/login", json={
            "email": test_email,
            "password": test_password
        })
        assert disabled_login.status_code == 403
        assert "desativada" in disabled_login.json()["detail"].lower()

    finally:
        # Restore settings
        settings.DISABLE_DASHBOARD_AUTH = original_disable_auth
        # Clean up database changes
        user = UserRepository.get_by_email(test_email)
        if user:
            UserRepository.delete(user["id"])
            print(f"Cleaned up test user: {test_email}")

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main(["-v", __file__]))
