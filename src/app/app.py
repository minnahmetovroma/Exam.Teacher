from src.routes.title import title_route
from src.routes.profile import profile_route
from src.routes.auth import auth_route
from src.routes.subjects import subjects_route

import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from src.config import BASE_DIR

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Exam.Teacher")

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(title_route)
app.include_router(profile_route)
app.include_router(auth_route)
app.include_router(subjects_route)


if __name__ == '__main__':
    uvicorn.run("src.app.app:app", host="127.0.0.1", port=32000, reload=True)


