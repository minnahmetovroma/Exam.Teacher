
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

title_route = APIRouter()

templates = Jinja2Templates(directory='templates')

@title_route.get('/')
async def title_list(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "Главная страница"}
    )