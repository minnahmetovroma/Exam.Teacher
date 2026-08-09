from fastapi import APIRouter, Request, Form, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from werkzeug.security import generate_password_hash, check_password_hash

from src import db
from src.dependencies.templating import templates
from src.schemas import UserRegistrationSchema

auth_route = APIRouter()


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
        if check_password_hash(user.password_hash, password):
            redirect = RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)
            redirect.set_cookie(key='user_id', value=user.id, httponly=True)
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

    try:
        UserRegistrationSchema.model_validate({
            'email': data['email'],
            'surname': data['surname'],
            'first_name': data['name'],
            'patronymic': data['patronymic'],
            'password_hash': data['password'],
            'repeat_password_hash': data['password_repeat'],
            'is_teacher': data['is_teacher'],
        })
    except ValidationError as exc:
        mismatch = any('Пароли не совпадают' in str(err['msg']) for err in exc.errors())
        title = 'Пароли не совпадают' if mismatch else 'Некорректные данные при регистрации'
        return RedirectResponse(
            url=f'/register/?title={title}',
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
