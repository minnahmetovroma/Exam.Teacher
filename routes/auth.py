from fastapi import APIRouter, Request, Form, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import db
from werkzeug.security import generate_password_hash, check_password_hash

auth_route = APIRouter()
templates = Jinja2Templates(directory='templates')


@auth_route.get('/login/')
async def login_get(request: Request, title: str = '', color: str = 'red'):
    return templates.TemplateResponse(
        request=request,
        name='login.html',
        context={'title': title, 'color': color}
    )

@auth_route.post('/login/')
async def login_post(
        request: Request,
        email: str = Form(...),
        password: str = Form(...)
):
    users = await db.get_user_by_email(email)

    if not users:
        return RedirectResponse(
            url='/login/?title=Такого пользователя нет', status_code=status.HTTP_303_SEE_OTHER,
        )

    for user in users:
        if check_password_hash(user['password_hash'], password):
            redirect = RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)
            redirect.set_cookie(key='user_id', value=user['id'], httponly=True)
            return redirect

    return RedirectResponse(
            url='/login/?title=Неверный пароль', status_code=status.HTTP_303_SEE_OTHER,
        )

@auth_route.get('/register/')
async def register_get(request: Request, title='', color='red'):
    return templates.TemplateResponse(
        request=request,
        name='register.html',
        context={'title': title, 'color': color}
    )

@auth_route.post('/register/')
async def register_post(request: Request):
    form = await request.form()
    data = dict(form)

    if data['password'] != data['password_repeat']:
        return RedirectResponse(
            url='/register/?title=Пароли не совпадают',
            status_code=status.HTTP_303_SEE_OTHER
        )
    if await db.is_in_users(data):
        return RedirectResponse(
            url='/register/?title=Такой пользователь уже создан',
            status_code=status.HTTP_303_SEE_OTHER
        )
    data['password_hash'] = generate_password_hash(data['password'])

    if data["is_teacher"] == 'yes':
        data["is_teacher"] = 1
    else:
        data["is_teacher"] = 0

    data.pop('password', None)
    data.pop('password_repeat', None)

    await db.add_new_user(data)

    return RedirectResponse(
        url="/login/?title=Вы зарегистрировались, войдите&color=green",
        status_code=status.HTTP_303_SEE_OTHER
    )


@auth_route.get('/logout/')
async def logout():
    redirect = RedirectResponse(url="/login/", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie("user_id")
    return redirect
