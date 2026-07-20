from app.models.user import UserCreate
from app.utils.security import hash_password, create_access_token

class AuthService:
    @staticmethod
    def register_user(user: UserCreate):
        hashed = hash_password(user.password)

        # TODO: Save the user to the database
        return {
            "email": user.email,
            "message": "User registered"
        }

    @staticmethod
    def login(email: str, password: str):
        # TODO: Verify the email and password from the database

        token = create_access_token({"sub": email})

        return {
            "access_token": token,
            "token_type": "bearer"
        }