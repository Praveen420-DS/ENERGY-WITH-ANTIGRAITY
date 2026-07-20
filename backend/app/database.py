from motor.motor_asyncio import AsyncIOMotorClient
from app.config import Settings

settings = Settings()
client: AsyncIOMotorClient | None = None

def get_database():
    if client is None:
        raise RuntimeError("Database client is not initialized")
    return client.get_default_database()

async def connect_db(uri: str = None):
    global client
    if uri is None:
        uri = settings.database_url
    client = AsyncIOMotorClient(uri)

async def disconnect_db():
    global client
    if client is not None:
        client.close()
