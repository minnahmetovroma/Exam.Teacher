
from fastapi import APIRouter, Request

from src.dependencies.templating import templates

title_route = APIRouter()

@title_route.get('/')
async def title_list(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "Главная страница"}
    )