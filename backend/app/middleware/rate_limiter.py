from fastapi import Request

async def rate_limiter(request: Request, call_next):
    response = await call_next(request)
    return response
