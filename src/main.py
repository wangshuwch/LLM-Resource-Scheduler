from fastapi import FastAPI
import uvicorn

from config.settings import settings


app = FastAPI(title=settings.app_name, debug=settings.debug)


@app.get("/")
async def root():
    return {
        "app_name": settings.app_name,
        "status": "healthy"
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
