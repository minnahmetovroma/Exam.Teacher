
from routes.title import title_route
from routes.profile import profile_route
from routes.auth import auth_route
from routes.subjects import subjects_route

from fastapi import FastAPI
import uvicorn


app = FastAPI(title="Exam.Teacher")

app.include_router(title_route)
app.include_router(profile_route)
app.include_router(auth_route)
app.include_router(subjects_route)


if __name__ == '__main__':
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)


