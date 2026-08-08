from fastapi import APIRouter, Request, Depends

from src.dependencies.dependencies import get_current_user
from src.schemas import UserReadSchema
from src.dependencies.templating import templates

profile_route = APIRouter()

@profile_route.get('/profile/')
async def profile_get(request: Request, user: UserReadSchema = Depends(get_current_user)):
    context = {
        "request": request,
        **user.model_dump()
    }
    return templates.TemplateResponse(
        request=request,
        name='profile.html',
        context=context
    )