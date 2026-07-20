from app.models.user import UserCreate, UserLogin
from app.utils.security import hash_password, create_access_token

class AuthService:
    @staticmethod
    def register_user(user: UserCreate):
        hashed = hash_password(user.password)
        return {"email": user.email, "message": "User registered"}

    @staticmethod
    def login_user(credentials: UserLogin):
        token = create_access_token({"sub": credentials.email})
        return {"access_token": token, "token_type": "bearer"}
