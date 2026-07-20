from fastapi.middleware.cors import CORSMiddleware

cors_config = {
    "allow_origins": ["*"],
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
