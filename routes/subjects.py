from os import makedirs, path
from shutil import copyfileobj
from uuid import uuid4
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
import db
from typing import List, Optional
import logging
from json import dumps

from dependencies import get_current_user

subjects_route = APIRouter()
templates = Jinja2Templates(directory="templates")


@subjects_route.get('/subjects/')
async def subjects_get(request: Request, user: dict = Depends(get_current_user)):
    all_subjects = await db.get_all_subjects(user_id=user['id'], is_teacher=user['is_teacher'])

    is_editor = user.get('is_editor', False)

    subject_ids = [s['id'] for s in all_subjects]
    redactor_ids = await db.get_redactor_subject_ids(subject_ids, user['id']) if subject_ids else set()

    for subject in all_subjects:
        subject['can_edit'] = is_editor or subject['id'] in redactor_ids

    return templates.TemplateResponse(
        request=request,
        name='subjects.html',
        context={
            "title": "Все предметы",
            "items": all_subjects,
            "user": user,
            "can_create": is_editor
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

@subjects_route.post('/subjects/{subject_id}/edit/')
async def edit_subject(
        subject_id: int,
        name: str = Form(""),
        description: str = Form(""),
        is_private: str = Form("false"),
        user: dict = Depends(get_current_user)
):
    is_editor = user.get('is_editor', False)
    is_subject_redactor = await db.is_user_subject_redactor(subject_id, user['id'])

    if not (is_editor or is_subject_redactor):
        raise HTTPException(status_code=403, detail="Нет прав на редактирование этого предмета.")

    is_public = is_private.lower() not in ("true", "1", "on", "yes")
    success = await db.update_subject(subject_id, name, description, is_public)

    if not success:
        raise HTTPException(status_code=500, detail="Ошибка при изменении предмета в базе данных.")

    return {
            "status": "success",
            "new_name": name,
            "new_description": description,
            "is_public": is_public
        }


@subjects_route.post('/subjects/{subject_id}/delete/')
async def delete_subject_endpoint(
        subject_id: int,
        user: dict = Depends(get_current_user)
):

    print("smth")
    is_editor = user.get('is_editor', False)
    is_subject_redactor = await db.is_user_subject_redactor(subject_id, user['id'])

    if not (is_editor or is_subject_redactor):
        raise HTTPException(status_code=403, detail="Нет прав на удаление этого предмета.")

    success = await db.delete_subject(subject_id)

    if not success:
        raise HTTPException(status_code=500, detail="Не удалось удалить предмет. Возможно, в нём есть темы.")

    return {"status": "success"}


@subjects_route.get('/subjects/{subject_id}/')
async def topics_get(request: Request, subject_id: int, user: dict = Depends(get_current_user)):
    subject = await db.get_subject_by_id(subject_id)

    if subject:
        topics = await db.get_topics_by_subject_id(subject_id, user['id'], user.get('is_teacher'))

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
        description: str = Form(""),
        is_private: bool = Form(False)
):
    is_editor = user.get('is_editor', False)
    is_subject_redactor = await db.is_user_subject_redactor(subject_id, user['id'])

    if not (is_editor or is_subject_redactor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет прав на добавление тем в этот предмет."
        )

    is_public = not is_private

    new_topic = await db.add_new_topic(
        name=name,
        description=description,
        user_id=user['id'],
        subject_id=subject_id,
        is_public_input=is_public
    )

    if not new_topic:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать тему из-за ошибки сервера или база данных недоступна."
        )

    return RedirectResponse(url=f'/subjects/{subject_id}/', status_code=303)

@subjects_route.post('/subjects/{subject_id}/{topic_id}/edit/')
async def edit_topic(
        subject_id: int,
        topic_id: int,
        name: str = Form(""),
        description: str = Form(""),
        is_private: str = Form("false"),
        user: dict = Depends(get_current_user)
):
    is_editor = user.get('is_editor', False)
    is_subject_redactor = await db.is_user_subject_redactor(subject_id, user['id'])
    is_topic_redactor = await db.is_user_topic_redactor(topic_id, user['id'])

    if not (is_editor or is_subject_redactor or is_topic_redactor):
        raise HTTPException(status_code=403, detail="Нет прав на редактирование этой темы.")

    is_public = is_private.lower() not in ("true", "1", "on", "yes")
    success = await db.update_topic(topic_id, name, description, is_public)

    if not success:
        raise HTTPException(status_code=500, detail="Ошибка при изменении темы в базе данных.")

    return {
            "status": "success",
            "new_name": name,
            "new_description": description,
            "is_public": is_public
        }


@subjects_route.post('/subjects/{subject_id}/{topic_id}/delete/')
async def delete_topic_endpoint(
        subject_id: int,
        topic_id: int,
        user: dict = Depends(get_current_user)
):
    is_editor = user.get('is_editor', False)
    is_subject_redactor = await db.is_user_subject_redactor(subject_id, user['id'])
    is_topic_redactor = await db.is_user_topic_redactor(topic_id, user['id'])

    if not (is_editor or is_subject_redactor or is_topic_redactor):
        raise HTTPException(status_code=403, detail="Нет прав на удаление этой темы.")

    success = await db.delete_topic(topic_id)

    if not success:
        raise HTTPException(status_code=500, detail="Не удалось удалить тему. Возможно, в ней остались задания.")

    return {"status": "success"}

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

        tasks = await db.get_tasks_by_topic_id(topic_id, user_id=user['id'], is_teacher=user.get('is_teacher'))

        if tasks is None:
            tasks = []

        attempts = {}
        if not user.get('is_teacher') and tasks:
            attempts = await db.get_student_attempts(user['id'], [t['id'] for t in tasks])

        return templates.TemplateResponse(
            request=request,
            name="tasks.html",
            context={
                "title": f"{topic['name']}",
                "items": tasks,
                "url": f"subjects/{subject_id}/{topic_id}",
                "user": user,
                "can_edit": can_edit,
                "attempts": attempts
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
        name: str = Form(...),
        description: str = Form(""),
        is_private: bool = Form(False),

        question_type: str = Form(...),

        correct_text: Optional[str] = Form(None),
        is_case_sensitive: Optional[int] = Form(0),

        options: List[str] = Form(None),
        correct_options: List[str] = Form(None),

        can_retry: bool = Form(False),

        task_attachments: List[UploadFile] = File(default=[])
):
    is_editor = user.get('is_editor', False)
    is_subject_redactor = await db.is_user_subject_redactor(subject_id, user['id'])
    is_topic_redactor = await db.is_user_topic_redactor(topic_id, user['id'])

    if not (is_editor or is_subject_redactor or is_topic_redactor):
        raise HTTPException(status_code=403, detail="У вас нет прав.")

    if question_type == 'choice' and (not correct_options or not any(o.strip() for o in correct_options if o)):
        raise HTTPException(status_code=400, detail="Выберите хотя бы один правильный вариант")
    if question_type == 'text' and (not correct_text or not correct_text.strip()):
        raise HTTPException(status_code=400, detail="Введите правильный ответ")

    is_material = (question_type == 'material')
    is_public = not is_private

    task_info = await db.add_new_task(
        name=name,
        topic_id=topic_id,
        description=description,
        user_id=user['id'],
        is_public_input=is_public,
        question_type=question_type,
        correct_text=correct_text,
        is_case_sensitive=is_case_sensitive,
        options=options,
        correct_options=correct_options,
        can_retry=can_retry,
        is_material=is_material
    )

    if not task_info:
        raise HTTPException(status_code=500, detail="Ошибка базы данных.")

    task_id = task_info['id']

    if task_attachments and task_attachments[0].filename:
        upload_dir = f"static/uploads/tasks/{task_id}"
        makedirs(upload_dir, exist_ok=True)

        for file in task_attachments:
            if file.filename:
                try:
                    ext = file.filename.split('.')[-1]
                    unique_filename = f"{uuid4().hex}.{ext}"
                    file_path = f"{upload_dir}/{unique_filename}"

                    with open(file_path, "wb") as buffer:
                        copyfileobj(file.file, buffer)

                    await db.add_task_attachment(task_id, file_path, file.filename)

                except Exception as e:
                    logging.error(f"Ошибка при сохранении файла {file.filename} для задания {task_id}: {e}")
                    pass

    return RedirectResponse(url=f'/subjects/{subject_id}/{topic_id}/', status_code=303)


@subjects_route.post('/subjects/{subject_id}/{topic_id}/{task_id}/edit/')
async def edit_task(
        subject_id: int,
        topic_id: int,
        task_id: int,
        name: str = Form(""),
        description: str = Form(""),
        is_private: bool = Form(False),
        question_type: Optional[str] = Form(None),
        correct_text: Optional[str] = Form(None),
        is_case_sensitive: Optional[int] = Form(0),
        options: List[str] = Form(None),
        correct_options: List[str] = Form(None),
        can_retry: bool = Form(False),
        task_attachments: List[UploadFile] = File(default=[]),
        user: dict = Depends(get_current_user)
):
    is_editor = user.get('is_editor', False)
    is_subject_redactor = await db.is_user_subject_redactor(subject_id, user['id'])
    is_topic_redactor = await db.is_user_topic_redactor(topic_id, user['id'])
    is_task_redactor = await db.is_user_task_redactor(task_id, user['id'])

    if not (is_editor or is_subject_redactor or is_topic_redactor or is_task_redactor):
        raise HTTPException(status_code=403, detail="Нет прав на редактирование задания.")

    if question_type == 'choice' and (not correct_options or not any(o.strip() for o in correct_options if o)):
        raise HTTPException(status_code=400, detail="Выберите хотя бы один правильный вариант")
    if question_type == 'text' and (not correct_text or not correct_text.strip()):
        raise HTTPException(status_code=400, detail="Введите правильный ответ")

    is_material = (question_type == 'material') if question_type else False
    is_public = not is_private
    ok = await db.update_task_fields(
        task_id, name, description, is_public,
        question_type=question_type,
        correct_text=correct_text,
        is_case_sensitive=is_case_sensitive,
        options=options,
        correct_options=correct_options,
        can_retry=can_retry,
        is_material=is_material
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Ошибка при сохранении изменений.")

    if task_attachments and task_attachments[0].filename:
        upload_dir = f"static/uploads/tasks/{task_id}"
        makedirs(upload_dir, exist_ok=True)

        for file in task_attachments:
            if file.filename:
                try:
                    ext = file.filename.split('.')[-1]
                    unique_filename = f"{uuid4().hex}.{ext}"
                    file_path = f"{upload_dir}/{unique_filename}"

                    with open(file_path, "wb") as buffer:
                        copyfileobj(file.file, buffer)

                    await db.add_task_attachment(task_id, file_path, file.filename)

                except Exception as e:
                    logging.error(f"Ошибка при сохранении файла {file.filename} для задания {task_id}: {e}")
                    pass

    return {
            "status": "success",
            "new_name": name,
            "new_description": description,
            "is_public": is_public
        }

@subjects_route.post('/subjects/{subject_id}/{topic_id}/{task_id}/delete/')
async def delete_task(
        subject_id: int,
        topic_id: int,
        task_id: int,
        user: dict = Depends(get_current_user)
):
    is_editor = user.get('is_editor', False)
    is_subject_redactor = await db.is_user_subject_redactor(subject_id, user['id'])
    is_topic_redactor = await db.is_user_topic_redactor(topic_id, user['id'])
    is_task_redactor = await db.is_user_task_redactor(task_id, user['id'])

    if not (is_editor or is_subject_redactor or is_topic_redactor or is_task_redactor):
        raise HTTPException(status_code=403, detail="Нет прав на удаление задания.")

    success = await db.delete_task(task_id)

    if not success:
        raise HTTPException(status_code=500, detail="Ошибка при удалении задания из БД.")

    return {"status": "success"}


@subjects_route.post('/subjects/{subject_id}/{topic_id}/{task_id}/check/')
async def check_answer_endpoint(
        request: Request,
        task_id: int,
        user: dict = Depends(get_current_user)
):
    task = await db.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задание не найдено")

    form_data = await request.form()

    is_correct = False
    answer_text = None
    file_path = None
    message = ""

    question_type = task.get('question_type')

    if question_type == 'choice':
        user_answers = form_data.getlist('user_answer')
        correct_options = task.get('correct_options', [])

        user_answers_str = [str(ans) for ans in user_answers]
        correct_options_str = [str(ans) for ans in correct_options]

        is_correct = set(user_answers_str) == set(correct_options_str)
        answer_text = dumps(user_answers_str)

        message = "Правильно! Отличная работа 🎉" if is_correct else "Неверно. Попробуй еще раз!"

    elif question_type == 'text':
        user_answer = form_data.get('user_answer', '').strip()
        correct_answer = str(task.get('correct_answer', '')).strip() if task.get('correct_answer') else ''
        is_case_sensitive = bool(task.get('is_case_sensitive', 0))

        if not is_case_sensitive:
            is_correct = (user_answer.lower() == correct_answer.lower())
        else:
            is_correct = (user_answer == correct_answer)

        answer_text = user_answer
        message = "Правильно! Отличная работа 🎉" if is_correct else "Неверно. Попробуй еще раз!"

    elif question_type == 'material':
        return JSONResponse(status_code=400, content={
            "is_correct": False,
            "message": "Конспект/материал — не требует ответа."
        })

    elif question_type == 'file':
        user_file = form_data.get('user_answer')

        if not hasattr(user_file, 'filename') or not user_file.filename:
            return JSONResponse(status_code=400, content={
                "is_correct": False,
                "message": "Ошибка: Файл не был прикреплен."
            })

        ext = user_file.filename.split('.')[-1]
        unique_filename = f"{uuid4().hex}.{ext}"

        upload_dir = f"static/uploads/student_answers/{user['id']}/{task_id}"
        makedirs(upload_dir, exist_ok=True)

        save_path = path.join(upload_dir, unique_filename)

        with open(save_path, "wb") as buffer:
            copyfileobj(user_file.file, buffer)

        file_path = save_path
        answer_text = user_file.filename
        is_correct = None

        message = "Файл успешно загружен и отправлен на проверку преподавателю! 📝"

    else:
        return JSONResponse(status_code=400, content={
            "is_correct": False,
            "message": "Неизвестный тип задания."
        })

    await db.save_student_attempt(
        user_id=user['id'],
        task_id=task_id,
        is_correct=is_correct,
        answer_text=answer_text,
        file_path=file_path
    )

    return {
        "is_correct": is_correct,
        "message": message
    }


@subjects_route.get('/users/search')
async def search_users(
    request: Request,
    q: str = '',
    user: dict = Depends(get_current_user)
):
    if not q.strip():
        return []

    users = await db.search_users(q.strip())
    return users


@subjects_route.get('/subjects/{subject_id}/redactors')
async def get_subject_redactors_list(subject_id: int, user: dict = Depends(get_current_user)):
    can_edit = await db.is_user_subject_redactor(subject_id, user['id'])
    if not can_edit:
        raise HTTPException(status_code=403)
    subject = await db.get_subject_by_id(subject_id)
    creator_id = subject['created_by'] if subject else None
    redactors = await db.get_subject_redactors(subject_id)
    for r in redactors:
        r['protected'] = (r['id'] == creator_id)
    return redactors


@subjects_route.get('/subjects/{subject_id}/students')
async def get_subject_students_list(subject_id: int, user: dict = Depends(get_current_user)):
    can_edit = await db.is_user_subject_redactor(subject_id, user['id'])
    if not can_edit:
        raise HTTPException(status_code=403)
    return await db.get_subject_students(subject_id)


@subjects_route.get('/subjects/{subject_id}/{topic_id}/redactors')
async def get_topic_redactors_list(subject_id: int, topic_id: int, user: dict = Depends(get_current_user)):
    can_edit = await db.is_user_topic_redactor(topic_id, user['id'])
    if not can_edit:
        raise HTTPException(status_code=403)
    topic_creator = await db.get_topic_creator(topic_id)
    subject_creator = await db.get_subject_creator(subject_id)
    redactors = await db.get_topic_redactors(topic_id)
    for r in redactors:
        r['protected'] = (r['id'] == topic_creator or r['id'] == subject_creator)
    return redactors


@subjects_route.get('/subjects/{subject_id}/{topic_id}/students')
async def get_topic_students_list(subject_id: int, topic_id: int, user: dict = Depends(get_current_user)):
    can_edit = await db.is_user_topic_redactor(topic_id, user['id'])
    if not can_edit:
        raise HTTPException(status_code=403)
    return await db.get_topic_students(topic_id)


@subjects_route.get('/subjects/{subject_id}/{topic_id}/{task_id}/redactors')
async def get_task_redactors_list(subject_id: int, topic_id: int, task_id: int, user: dict = Depends(get_current_user)):
    can_edit = await db.is_user_task_redactor(task_id, user['id'])
    if not can_edit:
        raise HTTPException(status_code=403)
    task = await db.get_task_by_id(task_id)
    task_creator = task.get('created_by') if task else None
    topic_creator = await db.get_topic_creator(topic_id)
    subject_creator = await db.get_subject_creator(subject_id)
    redactors = await db.get_task_redactors(task_id)
    for r in redactors:
        r['protected'] = (r['id'] == task_creator or r['id'] == topic_creator or r['id'] == subject_creator)
    return redactors


@subjects_route.get('/subjects/{subject_id}/{topic_id}/{task_id}/students')
async def get_task_students_list(subject_id: int, topic_id: int, task_id: int, user: dict = Depends(get_current_user)):
    can_edit = await db.is_user_task_redactor(task_id, user['id'])
    if not can_edit:
        raise HTTPException(status_code=403)
    return await db.get_task_students(task_id)


@subjects_route.get('/subjects/{subject_id}/{topic_id}/{task_id}/submissions')
async def get_task_submissions_list(subject_id: int, topic_id: int, task_id: int, user: dict = Depends(get_current_user)):
    can_edit = await db.is_user_task_redactor(task_id, user['id'])
    if not can_edit:
        raise HTTPException(status_code=403)
    return await db.get_task_submissions(task_id)


@subjects_route.post('/subjects/{subject_id}/{topic_id}/{task_id}/submissions/review')
async def review_submission(
    subject_id: int,
    topic_id: int,
    task_id: int,
    user: dict = Depends(get_current_user),
    user_id: int = Form(...),
    is_correct: int = Form(...),
):
    can_edit = await db.is_user_task_redactor(task_id, user['id'])
    if not can_edit:
        raise HTTPException(status_code=403)
    ok = await db.update_attempt_review(user_id, task_id, is_correct)
    if not ok:
        raise HTTPException(status_code=400, detail="Submission not found")
    return {"status": "ok"}


@subjects_route.get('/subjects/{subject_id}/{topic_id}/{task_id}/submissions/{user_id}/file')
async def get_submission_file(
    subject_id: int,
    topic_id: int,
    task_id: int,
    user_id: int,
    user: dict = Depends(get_current_user),
):
    can_edit = await db.is_user_task_redactor(task_id, user['id'])
    if not can_edit:
        raise HTTPException(status_code=403)
    file_path = await db.get_submission_file_path(user_id, task_id)
    if not file_path or not path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@subjects_route.get('/subjects/{subject_id}/{topic_id}/{task_id}/attachments/{att_id}/file')
async def get_task_attachment_file(
    subject_id: int,
    topic_id: int,
    task_id: int,
    att_id: int,
    user: dict = Depends(get_current_user),
):
    attachment = await db.get_task_attachment(att_id)
    if not attachment or attachment['task_id'] != task_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    file_path = attachment['file_path']
    if not path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@subjects_route.post('/subjects/{subject_id}/manage')
async def manage_subject(
    subject_id: int,
    user: dict = Depends(get_current_user),
    action: str = Form(...),
    target_user_id: int = Form(...),
    access_all_topics: bool = Form(False),
    access_all_tasks: bool = Form(False),
):
    is_editor = await db.is_user_subject_redactor(subject_id, user['id'])
    if not is_editor:
        raise HTTPException(status_code=403)

    if action == 'add_redactor':
        target_user = await db.get_user_by_id(target_user_id)
        if not target_user or not target_user['is_teacher']:
            raise HTTPException(status_code=400, detail="Можно добавить только учителя")
        ok = await db.add_subject_redactor(subject_id, target_user_id)
    elif action == 'remove_redactor':
        subject = await db.get_subject_by_id(subject_id)
        if subject and target_user_id == subject['created_by']:
            raise HTTPException(status_code=400, detail="Нельзя удалить создателя предмета")
        ok = await db.remove_subject_redactor(subject_id, target_user_id)
    elif action == 'add_student':
        ok = await db.add_student_subject(target_user_id, subject_id, access_all_topics, access_all_tasks)
    elif action == 'remove_student':
        ok = await db.remove_student_subject(target_user_id, subject_id)
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    if not ok:
        raise HTTPException(status_code=400, detail="Operation failed")

    return {"status": "ok"}


@subjects_route.post('/subjects/{subject_id}/{topic_id}/manage')
async def manage_topic(
    subject_id: int,
    topic_id: int,
    user: dict = Depends(get_current_user),
    action: str = Form(...),
    target_user_id: int = Form(...),
    access_all_tasks: bool = Form(False),
):
    is_editor = await db.is_user_topic_redactor(topic_id, user['id'])
    if not is_editor:
        raise HTTPException(status_code=403)

    if action == 'add_redactor':
        target_user = await db.get_user_by_id(target_user_id)
        if not target_user or not target_user['is_teacher']:
            raise HTTPException(status_code=400, detail="Можно добавить только учителя")
        ok = await db.add_topic_redactor(topic_id, target_user_id)
    elif action == 'remove_redactor':
        topic_creator = await db.get_topic_creator(topic_id)
        subject_creator = await db.get_subject_creator(subject_id)
        if target_user_id == topic_creator or target_user_id == subject_creator:
            raise HTTPException(status_code=400, detail="Нельзя удалить создателя")
        ok = await db.remove_topic_redactor(topic_id, target_user_id)
    elif action == 'add_student':
        ok = await db.add_student_topic(target_user_id, topic_id, access_all_tasks)
    elif action == 'remove_student':
        ok = await db.remove_student_topic(target_user_id, topic_id)
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    if not ok:
        raise HTTPException(status_code=400, detail="Operation failed")

    return {"status": "ok"}


@subjects_route.post('/subjects/{subject_id}/{topic_id}/{task_id}/manage')
async def manage_task(
    subject_id: int,
    topic_id: int,
    task_id: int,
    user: dict = Depends(get_current_user),
    action: str = Form(...),
    target_user_id: int = Form(...),
):
    is_editor = await db.is_user_task_redactor(task_id, user['id'])
    if not is_editor:
        raise HTTPException(status_code=403)

    if action == 'add_redactor':
        target_user = await db.get_user_by_id(target_user_id)
        if not target_user or not target_user['is_teacher']:
            raise HTTPException(status_code=400, detail="Можно добавить только учителя")
        ok = await db.add_task_redactor(task_id, target_user_id)
    elif action == 'remove_redactor':
        task = await db.get_task_by_id(task_id)
        task_creator = task.get('created_by') if task else None
        topic_creator = await db.get_topic_creator(topic_id)
        subject_creator = await db.get_subject_creator(subject_id)
        if target_user_id == task_creator or target_user_id == topic_creator or target_user_id == subject_creator:
            raise HTTPException(status_code=400, detail="Нельзя удалить создателя")
        ok = await db.remove_task_redactor(task_id, target_user_id)
    elif action == 'add_student':
        ok = await db.add_student_task(target_user_id, task_id)
    elif action == 'remove_student':
        ok = await db.remove_student_task(target_user_id, task_id)
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    if not ok:
        raise HTTPException(status_code=400, detail="Operation failed")

    return {"status": "ok"}
