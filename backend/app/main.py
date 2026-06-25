from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import chat, feedback, museums, narrate, recognize

app = FastAPI(title="Museum Guide API", version="0.1.0")

# 静态文件（博物馆图片等）
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(museums.router)
app.include_router(recognize.router)
app.include_router(narrate.router)
app.include_router(chat.router)
app.include_router(feedback.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
