from sqlalchemy import text

from app.database import engine


class SystemService:
    @staticmethod
    async def health_check() -> dict[str, str]:
        db_status = "ok"
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            db_status = "unavailable"
        return {"status": "ok", "database": db_status}
