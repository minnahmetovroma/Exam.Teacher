from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import db

from dependencies import get_current_user

subjects_route = APIRouter()
templates = Jinja2Templates(directory="templates")

@subjects_route.get('/subjects/')
async def subjects_get(request: Request, user: dict = Depends(get_current_user)):
    all_subjects = await db.get_all_subjects()
    return templates.TemplateResponse(
        request=request,
        name='list.html',
        context={
            "title": "Все предметы",
            "items": all_subjects,
            "url": "subjects",
            "user": user
        }
    )

@subjects_route.post('/subjects/')
async def create_subjects(
        request: Request,
        user: dict = Depends(get_current_user),
        name = Form(...),
        description = Form(None),
):
    await db.add_new_subject(name=name, description=description, user_id=user['id'])
    return RedirectResponse(url="/subjects/", status_code=303)

@subjects_route.get('/subjects/{subject_id}/')
async def topics_get(request: Request, subject_id: int, user: dict = Depends(get_current_user)):
    subject = await db.get_subject_by_id(subject_id)
    topics = await db.get_topics_by_subject_id(subject_id)
    if subject:
        items = topics if topics else [{'name': "Тем пока нет"}]
        return templates.TemplateResponse(
            request=request,
            name="list.html",
            context={
                "title": f"{subject['name']}",
                "items": items,
                "url": f"subjects/{subject_id}",
                "user": user
            }
        )
    else:
        return templates.TemplateResponse(
            request=request,
            name="list.html",
            context={
                "title": "Такого предмета нет",
                "items": {},
                "url": f"subjects/{subject_id}",
                "user": user
            }
        )

@subjects_route.post('/subjects/{subject_id}/')
async def create_topic(
        request: Request,
        subject_id: int,
        user: dict = Depends(get_current_user),
        name=Form(...),
        description=Form(None),
):
    await db.add_new_topic(
        name=name,
        description=description,
        user_id=user['id'],
        subject_id=subject_id
    )

    return RedirectResponse(url=f'/subjects/{subject_id}/', status_code=303)


@subjects_route.get('/subjects/{subject_id}/{topic_id}/')
async def tasks_list(
        request: Request,
        subject_id: int,
        topic_id: int,
        user: dict = Depends(get_current_user)
):
    topic = await db.get_topic_by_id(topic_id)

    if topic:
        topic_name = topic['name']
        tasks = await db.get_tasks_by_topic_id(topic_id)

        items = tasks if tasks else [{'name': "Задач пока нет"}]
        return templates.TemplateResponse(
            request=request,
            name="tasks.html",
            context={
                "title": f"{topic_name}",
                "items": items,
                "url": f"subjects/{subject_id}/{topic_id}",
                "user": user
            }
        )
    else:
        return templates.TemplateResponse(
            request=request,
            name="list.html",
            context={
                "title": "Такой темы нет",
                "items": [],
                "url": f"subjects/{subject_id}",
                "user": user
            }
        )