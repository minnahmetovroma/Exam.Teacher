from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from dependencies import get_current_user

profile_route = APIRouter()

templates = Jinja2Templates(directory='templates')

@profile_route.get('/profile/')
async def profile_get(request: Request, user=Depends(get_current_user)):
    context = {
        "request": request,
        **user
    }
    return templates.TemplateResponse(
        request=request,
        name='profile.html',
        context=context
    )