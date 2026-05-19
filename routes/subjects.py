from os import makedirs
from shutil import copyfileobj
from uuid import uuid4
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import db
from typing import List
import logging

from dependencies import get_current_user

subjects_route = APIRouter()
templates = Jinja2Templates(directory="templates")

@subjects_route.get('/subjects/')
async def subjects_get(request: Request, user: dict = Depends(get_current_user)):
    all_subjects = await db.get_all_subjects(user_id=user['id'], is_teacher=user['is_teacher'])
    return templates.TemplateResponse(
        request=request,
        name='list.html',
        context={
            "title": "Все предметы",
            "items": all_subjects,
            "url": "subjects",
            "user": user,
            "can_edit": True
        }
    )


@subjects_route.post('/subjects/')
async def create_subject(
        request: Request,
        name: str = Form(...),
        description: str = Form(""),
        is_public: bool = Form(True),
        user: dict = Depends(get_current_user)
):
    if not user.get('is_teacher', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только учителя могут создавать предметы."
        )
    new_subject = await db.add_new_subject(
        name=name,
        description=description,
        user_id=user['id'],
        is_public=is_public
    )

    if not new_subject:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать предмет из-за ошибки базы данных."
        )

    return RedirectResponse(url='/subjects/', status_code=303)


@subjects_route.get('/subjects/{subject_id}/')
async def topics_get(request: Request, subject_id: int, user: dict = Depends(get_current_user)):
    subject = await db.get_subject_by_id(subject_id)

    if subject:
        topics = await db.get_topics_by_subject_id(subject_id)

        if topics is None:
            topics = []


        can_edit = await db.is_user_subject_redactor(subject_id, user.get('id'))

        return templates.TemplateResponse(
            request=request,
            name="list.html",
            context={
                "title": f"{subject['name']}",
                "items": topics,
                "url": f"subjects/{subject_id}",
                "user": user,
                "can_edit": can_edit
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="list.html",
        context={
            "title": "Такого предмета нет",
            "url": f"subjects/{subject_id}",
            "user": user
        }
    )

@subjects_route.post('/subjects/{subject_id}/')
async def create_topic(
        request: Request,
        subject_id: int,
        user: dict = Depends(get_current_user),
        name: str = Form(...),
        description: str = Form(None),
        is_private: bool = Form(False)
):
    # 1. ПРОВЕРКА ПРАВ ДОСТУПА
    is_editor = user.get('is_editor', False)
    is_subject_redactor = await db.is_user_subject_redactor(subject_id, user['id'])

    if not (is_editor or is_subject_redactor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет прав на добавление тем в этот предмет."
        )

    # 2. Конвертируем is_private в is_public
    is_public = not is_private

    # 3. Создаем тему и привязываем редактора одной транзакцией
    new_topic = await db.add_new_topic(
        name=name,
        description=description,
        user_id=user['id'],
        subject_id=subject_id,
        is_public_input=is_public
    )

    # 4. Если база вернула пустой словарь — значит, был сбой (отработал rollback)
    if not new_topic:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать тему из-за ошибки сервера или база данных недоступна."
        )

    # 5. Если всё ок, перенаправляем на страницу предмета
    return RedirectResponse(url=f'/subjects/{subject_id}/', status_code=303)


@subjects_route.get('/subjects/{subject_id}/{topic_id}/')
async def tasks_list(
        request: Request,
        subject_id: int,
        topic_id: int,
        user: dict = Depends(get_current_user)
):
    topic = await db.get_topic_by_id(topic_id)
    subject = await db.get_subject_by_id(subject_id)

    if topic and subject:
        can_edit = await db.is_user_topic_redactor(topic_id, user.get('id'))

        tasks = await db.get_tasks_by_topic_id(topic_id)

        if tasks is None:
            tasks = []

        return templates.TemplateResponse(
            request=request,
            name="tasks.html",
            context={
                "title": f"{topic['name']}",
                "items": tasks,
                "url": f"subjects/{subject_id}/{topic_id}",
                "user": user,
                "can_edit": can_edit  # <-- Передаем флаг!
            }
        )

    return templates.TemplateResponse(
            request=request,
            name="list.html",
            context={
                "title": "Такой темы нет",
                "url": f"subjects/{subject_id}",
                "user": user
            }
        )


@subjects_route.post('/subjects/{subject_id}/{topic_id}/')
async def create_task(
        request: Request,
        subject_id: int,
        topic_id: int,
        user: dict = Depends(get_current_user),
        description: str = Form(""),
        is_private: bool = Form(False),
        # ... ТВОИ ОСТАЛЬНЫЕ ПОЛЯ ФОРМЫ (например, баллы, ответ) ...
        task_attachments: List[UploadFile] = File(default=[])  # Поле для файлов
):
    # 1. ПРОВЕРКА ПРАВ ДОСТУПА
    is_editor = user.get('is_editor', False)
    is_subject_redactor = await db.is_user_subject_redactor(subject_id, user['id'])
    is_topic_redactor = await db.is_user_topic_redactor(topic_id, user['id'])

    if not (is_editor or is_subject_redactor or is_topic_redactor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет прав на добавление заданий в эту тему."
        )

    # 2. СОЗДАНИЕ ЗАДАНИЯ В БД
    is_public = not is_private

    # Вызываем твою функцию создания задания (убедись, что она тоже имеет rollback() внутри)
    task_info = await db.add_new_task(
        topic_id=topic_id,
        description=description,
        user_id=user['id'],
        is_public_input=is_public
        # ... передай сюда остальные параметры ...
    )

    # Если БД отвалилась и функция вернула пустой словарь
    if not task_info:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать задание из-за ошибки базы данных."
        )

    task_id = task_info['id']

    # 3. ОБРАБОТКА И СОХРАНЕНИЕ ФАЙЛОВ
    # Проверяем, что файлы действительно прикрепили
    if task_attachments and task_attachments[0].filename:
        upload_dir = f"static/uploads/tasks/{task_id}"
        makedirs(upload_dir, exist_ok=True)  # Создаем папку под задание

        for file in task_attachments:
            if file.filename:
                try:
                    # Генерируем уникальное имя файла, сохраняя оригинальное расширение
                    ext = file.filename.split('.')[-1]
                    unique_filename = f"{uuid4().hex}.{ext}"
                    file_path = f"{upload_dir}/{unique_filename}"

                    # Сохраняем физически на диск
                    with open(file_path, "wb") as buffer:
                        copyfileobj(file.file, buffer)

                    # Записываем в базу данных
                    await db.add_task_attachment(task_id, file_path, file.filename)

                except Exception as e:
                    # Если один файл не загрузился, логируем и продолжаем грузить остальные
                    logging.error(f"Ошибка при сохранении файла {file.filename} для задания {task_id}: {e}")
                    pass

                    # 4. ВОЗВРАТ НА СТРАНИЦУ ТЕМЫ
    return RedirectResponse(url=f'/subjects/{subject_id}/{topic_id}/', status_code=303)