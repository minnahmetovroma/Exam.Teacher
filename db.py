import logging
from typing import Optional

from aiomysql import connect, DictCursor
import os
from dotenv import load_dotenv
import json

async def get_connection():
    load_dotenv()
    host=os.getenv("DB_HOST")
    user=os.getenv("DB_USER")
    password=os.getenv("DB_PASSWORD")
    db=os.getenv("DB_NAME")
    try:
        connection = await connect(
            host=host,
            user=user,
            password=password,
            db=db,
            cursorclass=DictCursor
        )

        return connection
    except Exception as e:
        logging.error(f"Ошибка подключения: {e}")
        return None

async def get_all_subjects(user_id: int, is_teacher: bool):
    connection = await get_connection()

    if connection is None:
        return []
    try:
        async with connection.cursor() as cursor:
            if is_teacher:
                sql = """
                SELECT DISTINCT s.* FROM subjects s
                LEFT JOIN subject_redactors sr ON s.id = sr.subject_id
                WHERE s.created_by = %s 
                OR sr.user_id = %s 
                OR s.is_public = 1
                """
                await cursor.execute(sql, (user_id, user_id))

            else:
                sql = """
                SELECT DISTINCT s.* FROM subjects s
                LEFT JOIN student_subjects ss ON s.id = ss.subject_id
                WHERE ss.student_id = %s 
                OR s.is_public = 1
                """
                await cursor.execute(sql, (user_id,))

            return await cursor.fetchall()
    except Exception as e:
        logging.error(f"Ошибка при запросе предметов: {e}")
        return []
    finally:
        connection.close()


async def get_subject_by_id(subject_id: int):
    connection = await get_connection()

    if connection is None:
        return []
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT name, description, created_by FROM subjects WHERE id = %s", (subject_id, ))
            return await cursor.fetchone()
    except Exception as e:
        logging.error(f"Ошибка при запросе предмета: {e}")
        return []
    finally:
        connection.close()


async def get_subject_creator(subject_id: int) -> int | None:
    subject = await get_subject_by_id(subject_id)
    return subject.get('created_by') if subject else None


async def get_topic_creator(topic_id: int) -> int | None:
    topic = await get_topic_by_id(topic_id)
    return topic.get('created_by') if topic else None



async def get_topics_by_subject_id(subject_id: int, user_id: int = None, is_teacher: bool = False):
    connection = await get_connection()
    if connection is None:
        return []

    try:
        async with connection.cursor() as cursor:
            if is_teacher or user_id is None:
                await cursor.execute("SELECT * FROM topics WHERE subject_id = %s", (subject_id,))
            else:
                sql = """
                    SELECT t.* FROM topics t
                    LEFT JOIN student_subjects ss ON ss.subject_id = t.subject_id AND ss.student_id = %s
                    LEFT JOIN student_topics st ON st.topic_id = t.id AND st.student_id = %s
                    WHERE t.subject_id = %s
                      AND (t.is_public = 1
                           OR ss.access_all_topics = 1
                           OR st.student_id IS NOT NULL)
                """
                await cursor.execute(sql, (user_id, user_id, subject_id))
            return await cursor.fetchall()
    except Exception as e:
        logging.error(f"Ошибка при запросе тем: {e}")
        return []
    finally:
        connection.close()

async def get_tasks_by_topic_id(topic_id: int, only_public: bool = False, user_id: int = None, is_teacher: bool = False):
    connection = await get_connection()
    try:
        async with connection.cursor() as cursor:
            sql = """
                SELECT t.*, 
                       c.options, c.correct_options, c.multiple_correct, c.shuffle_options,
                       txt.correct_answer, txt.is_case_sensitive, txt.max_length,
                       f.max_file_size, f.allowed_types, f.is_material
                FROM tasks t
                LEFT JOIN choice_tasks c ON t.id = c.task_id
                LEFT JOIN text_tasks txt ON t.id = txt.task_id
                LEFT JOIN file_tasks f ON t.id = f.task_id
            """

            params = []
            if is_teacher or user_id is None:
                sql += " WHERE t.topic_id = %s"
                params.append(topic_id)
                if only_public:
                    sql += " AND t.is_public = 1"
            else:
                sql += """
                    JOIN topics tp ON t.topic_id = tp.id
                    LEFT JOIN student_subjects ss ON ss.subject_id = tp.subject_id AND ss.student_id = %s
                    LEFT JOIN student_topics st ON st.topic_id = t.topic_id AND st.student_id = %s
                    LEFT JOIN student_tasks sst ON sst.task_id = t.id AND sst.student_id = %s
                    WHERE t.topic_id = %s
                      AND (t.is_public = 1
                           OR ss.access_all_tasks = 1
                           OR st.access_all_tasks = 1
                           OR sst.student_id IS NOT NULL)
                """
                params.extend([user_id, user_id, user_id, topic_id])
                if only_public:
                    sql += " AND t.is_public = 1"

            await cursor.execute(sql, tuple(params))
            tasks = await cursor.fetchall()

            if not tasks:
                return []

            # Достаем все файлы для найденных заданий одним запросом
            task_ids = [t['id'] for t in tasks]
            format_strings = ','.join(['%s'] * len(task_ids))
            await cursor.execute(
                f"SELECT * FROM task_attachments WHERE task_id IN ({format_strings})",
                tuple(task_ids)
            )
            attachments = await cursor.fetchall()

            # Приклеиваем файлы к соответствующим заданиям
            for task in tasks:
                task['attachments'] = [a for a in attachments if a['task_id'] == task['id']]

            # Парсим JSON-поля
            json_fields = ['options', 'correct_options', 'allowed_types']
            for task in tasks:
                for field in json_fields:
                    if task.get(field) and isinstance(task[field], str):
                        try:
                            task[field] = json.loads(task[field])
                        except json.JSONDecodeError:
                            pass

            return tasks
    except Exception as e:
        logging.error(f"Ошибка при запросе заданий: {e}")
        return []
    finally:
        connection.close()

async def get_topic_by_id(topic_id):
    connection = await get_connection()

    if connection is None:
        return []
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT name, created_by FROM topics WHERE id = %s", (topic_id,))
            return await cursor.fetchone()
    except Exception as e:
        logging.error(f"Ошибка при запросе задания: {e}")
        return []
    finally:
        connection.close()

async def is_in_users(data: dict[str: str]) -> bool:
    connection = await get_connection()

    if connection is None:
        print("Error")
        return False
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT id FROM users WHERE surname = %s AND first_name = %s AND patronymic = %s AND email = %s",
                                 (data["surname"], data["name"], data["patronymic"], data["email"]))
            return True if await cursor.fetchone() else False
    except Exception as e:
        logging.error(f"Ошибка проверки пользователя: {e}")
        return False
    finally:
        connection.close()



async def add_new_user(data):
    connection = await get_connection()

    if connection is None:
        return
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("INSERT INTO users (surname, first_name, patronymic, email, password_hash, is_teacher) VALUES"
                           "(%s, %s, %s, %s, %s, %s)",
                           (data["surname"], data["name"], data["patronymic"], data["email"], data["password_hash"], data["is_teacher"]))

            await connection.commit()
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка при добавлении пользователя: {e}")
        return False
    finally:
        connection.close()

async def get_user_by_email(email: str):
    connection = await get_connection()

    if connection is None:
        return []
    try:
        async with connection.cursor() as cursor:

            await cursor.execute("SELECT * FROM users WHERE email = %s",
                           (email,))

            return await cursor.fetchall()
    except Exception as e:
        logging.error(f"Ошибка при запросе пользователя по почте: {e}")
        return []
    finally:
        connection.close()

async def get_user_by_id(id: int):
    connection = await get_connection()

    if connection is None:
        return []
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT * FROM users WHERE id = %s LIMIT 1",
                           (id,))

            return await cursor.fetchone()
    except Exception as e:
        logging.error(f"Ошибка при запросе пользователя по почте: {e}")
        return []

    finally:
        connection.close()


async def search_users(query: str) -> list[dict]:
    words = [w.strip() for w in query.strip().split() if w.strip()][:5]
    if not words:
        return []

    connection = await get_connection()
    if connection is None:
        return []

    try:
        async with connection.cursor() as cursor:
            search_terms = ' '.join(f"+{word}*" for word in words)
            sql = """
                SELECT id, first_name, surname, patronymic, email, is_teacher
                FROM users
                WHERE MATCH(first_name, surname, email) AGAINST(%s IN BOOLEAN MODE)
                LIMIT 20
            """
            await cursor.execute(sql, (search_terms,))
            return await cursor.fetchall() or []
    except Exception as e:
        logging.error(f"Ошибка поиска пользователей: {e}")
        return []
    finally:
        connection.close()


async def add_new_subject(name: str, description: str, user_id: int, is_public: bool = True) -> dict:
    connection = await get_connection()

    if connection is None:
        logging.error("Не удалось получить подключение к БД в add_new_subject")
        return {}

    try:
        async with connection.cursor() as cursor:
            # 1. Создаем предмет
            await cursor.execute(
                "INSERT INTO subjects (name, description, created_by, is_public) VALUES (%s, %s, %s, %s)",
                (name, description, user_id, is_public)
            )
            subject_id = cursor.lastrowid

            # 2. Сразу привязываем учителя как редактора
            await cursor.execute(
                "INSERT INTO subject_redactors (subject_id, user_id) VALUES (%s, %s)",
                (subject_id, user_id)
            )

            # 3. Применяем изменения разом (Транзакция)
            await connection.commit()

            return {
                'id': str(subject_id),
                'name': name,
                'description': description,
                'created_by': user_id,
                'is_public': is_public
            }

    except Exception as e:
        # Если хоть один INSERT упал — отменяем всё! Никаких "осиротевших" предметов.
        await connection.rollback()
        logging.error(f"Ошибка при создании предмета '{name}': {e}")
        return {}

    finally:
        connection.close()

async def add_new_topic(name: str, description: str, user_id: int, subject_id: int, is_public_input: bool) -> dict:
    connection = await get_connection()
    if connection is None:
        logging.error("Не удалось получить подключение к БД в add_new_topic")
        return {}

    try:
        async with connection.cursor() as cursor:
            # Получаем статус публичности предмета
            await cursor.execute("SELECT is_public FROM subjects WHERE id = %s", (subject_id,))
            subject = await cursor.fetchone()

            # Защита от создания темы в несуществующем предмете
            if not subject:
                logging.warning(f"Попытка добавить тему в несуществующий предмет (ID: {subject_id})")
                return {}

            subject_is_public = subject.get('is_public') if subject else 0
            final_is_public = 1 if (subject_is_public and is_public_input) else 0

            # 1. Добавляем саму тему
            sql = """
                INSERT INTO topics (name, description, created_by, subject_id, is_public) 
                VALUES (%s, %s, %s, %s, %s)
            """
            await cursor.execute(sql, (name, description, user_id, subject_id, final_is_public))
            topic_id = cursor.lastrowid

            # 2. Сразу же привязываем редактора (создателя) к этой теме
            await cursor.execute(
                "INSERT INTO topic_redactors (topic_id, user_id) VALUES (%s, %s)",
                (topic_id, user_id)
            )

            # 3. Фиксируем изменения (транзакция)
            await connection.commit()
            return {'id': topic_id, 'is_public': final_is_public}

    except Exception as e:
        # Отменяем всё при любой ошибке (например, если topic_redactors упадет)
        await connection.rollback()
        logging.error(f"Ошибка при добавлении темы '{name}' к предмету {subject_id}: {e}")
        return {}

    finally:
        connection.close()

# async def add_new_task(name: str, description: str, topic_id: int, user_id: int, question_type: str,
#                        is_public_input: bool):
#     connection = await get_connection()
#     if not connection:
#         return {}
#
#     try:
#         async with connection.cursor() as cursor:
#             # 1. Наследование приватности: проверяем статус родительской темы
#             await cursor.execute("SELECT is_public FROM topics WHERE id = %s", (topic_id,))
#             topic = await cursor.fetchone()
#             topic_is_public = topic.get('is_public') if topic else 0
#
#             # Задание публично ТОЛЬКО если тема публична И учитель не поставил галочку "Скрыть"
#             final_is_public = 1 if (topic_is_public and is_public_input) else 0
#
#             # 2. Создаем задание в базовой таблице
#             sql_task = """
#                 INSERT INTO tasks (name, description, topic_id, created_by, question_type, is_public)
#                 VALUES (%s, %s, %s, %s, %s, %s)
#             """
#             await cursor.execute(sql_task, (name, description, topic_id, user_id, question_type, final_is_public))
#             task_id = cursor.lastrowid
#
#             # 3. Создаем "скелет" в соответствующей дочерней таблице
#             if question_type == 'text':
#                 # Для текста пока просто привязываем ID
#                 await cursor.execute("INSERT INTO text_tasks (task_id) VALUES (%s)", (task_id,))
#
#             elif question_type == 'file':
#                 # Для файлов задаем дефолтные значения (например, 5 МБ и базовые форматы)
#                 default_types = '["pdf", "doc", "docx"]'
#                 await cursor.execute(
#                     "INSERT INTO file_tasks (task_id, max_file_size, allowed_types) VALUES (%s, %s, %s)",
#                     (task_id, 5242880, default_types)
#                 )
#
#             elif question_type == 'choice':
#                 # Для тестов создаем пустые массивы
#                 await cursor.execute(
#                     "INSERT INTO choice_tasks (task_id, options, correct_options, multiple_correct, shuffle_options) VALUES (%s, %s, %s, %s, %s)",
#                     (task_id, '[]', '[]', 0, 1)
#                 )
#
#             await connection.commit()
#             return {'id': task_id, 'question_type': question_type}
#
#     except Exception as e:
#         await connection.rollback()
#         print(f"Ошибка при создании задания: {e}")
#         return {}
#     finally:
#         connection.close()
# def get_subject_id_by_subject_name(subject_name):

async def add_new_task(
        topic_id: int,
        name: str,
        description: str,
        user_id: int,
        is_public_input: bool,
        question_type: str,  # Новый параметр
        correct_text: str = None,  # Новый параметр
        is_case_sensitive: int = 0,  # Новый параметр
        options: list = None,  # Новый параметр
        correct_options: list = None,  # Новый параметр
        can_retry: bool = False,
        is_material: bool = False
) -> dict:
    connection = await get_connection()
    if connection is None:
        logging.error("Не удалось получить подключение к БД в add_new_task")
        return {}

    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT is_public FROM topics WHERE id = %s", (topic_id,))
            topic = await cursor.fetchone()

            if not topic:
                return {}

            topic_is_public = topic.get('is_public') if topic else 0
            final_is_public = 1 if (topic_is_public and is_public_input) else 0

            sql = """
                INSERT INTO tasks (name, topic_id, description, created_by, is_public, question_type, can_retry) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            await cursor.execute(sql, (name, topic_id, description, user_id, final_is_public, question_type, int(can_retry)))
            task_id = cursor.lastrowid

            if question_type == 'text':
                sql_text = """
                    INSERT INTO text_tasks (task_id, correct_answer, is_case_sensitive) 
                    VALUES (%s, %s, %s)
                """
                await cursor.execute(sql_text, (task_id, correct_text, is_case_sensitive))

            elif question_type == 'choice':
                opts_json = json.dumps(options) if options else '[]'
                cor_opts_json = json.dumps(correct_options) if correct_options else '[]'
                multiple = 1 if correct_options and len(correct_options) > 1 else 0

                sql_choice = """
                    INSERT INTO choice_tasks (task_id, options, correct_options, multiple_correct) 
                    VALUES (%s, %s, %s, %s)
                """
                await cursor.execute(sql_choice, (task_id, opts_json, cor_opts_json, multiple))

            elif question_type == 'file':
                await cursor.execute(
                    "INSERT INTO file_tasks (task_id, is_material) VALUES (%s, %s)",
                    (task_id, int(is_material))
                )

            elif question_type == 'material':
                await cursor.execute(
                    "INSERT INTO file_tasks (task_id, is_material) VALUES (%s, %s)",
                    (task_id, 1)
                )

            # 3. Права редакторов
            await cursor.execute(
                "INSERT INTO task_redactors (task_id, user_id) VALUES (%s, %s)",
                (task_id, user_id)
            )

            await connection.commit()
            return {'id': task_id, 'is_public': final_is_public}

    except Exception as e:
        await connection.rollback()  # Если ошибка хоть в одной таблице - откатывается ВСЁ
        logging.error(f"Ошибка при добавлении задания: {e}")
        return {}

    finally:
        connection.close()

async def add_task_attachment(task_id: int, file_path: str, file_name: str):
    connection = await get_connection()
    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO task_attachments (task_id, file_path, file_name) VALUES (%s, %s, %s)",
                (task_id, file_path, file_name)
            )
            await connection.commit()
    except Exception as e:
        await connection.rollback()
        print(f"Ошибка при создании задания: {e}")
    finally:
        connection.close()


async def get_task_attachment(attachment_id: int) -> dict | None:
    connection = await get_connection()
    if connection is None:
        return None
    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM task_attachments WHERE id = %s",
                (attachment_id,)
            )
            return await cursor.fetchone()
    except Exception as e:
        logging.error(f"Ошибка получения attachment {attachment_id}: {e}")
        return None
    finally:
        connection.close()


async def is_user_subject_redactor(subject_id: int, user_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "SELECT 1 FROM subject_redactors WHERE subject_id = %s AND user_id = %s",
                (subject_id, user_id)
            )
            result = await cursor.fetchone()
            return result is not None

    except Exception as e:
        logging.error(f"Ошибка БД при проверке прав (subject: {subject_id}, user: {user_id}): {e}")
        return False

    finally:
        connection.close()


async def get_subject_redactors(subject_id: int) -> list[dict]:
    connection = await get_connection()
    if connection is None:
        return []

    try:
        async with connection.cursor() as cursor:
            await cursor.execute("""
                SELECT u.id, u.first_name, u.surname, u.patronymic, u.email
                FROM subject_redactors sr
                JOIN users u ON sr.user_id = u.id
                WHERE sr.subject_id = %s
            """, (subject_id,))
            return await cursor.fetchall() or []
    except Exception as e:
        logging.error(f"Ошибка при получении редакторов subject {subject_id}: {e}")
        return []
    finally:
        connection.close()


async def add_subject_redactor(subject_id: int, user_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "INSERT IGNORE INTO subject_redactors (subject_id, user_id) VALUES (%s, %s)",
                (subject_id, user_id)
            )
            await connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка добавления редактора subject {subject_id}, user {user_id}: {e}")
        return False
    finally:
        connection.close()


async def remove_subject_redactor(subject_id: int, user_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM subject_redactors WHERE subject_id = %s AND user_id = %s",
                (subject_id, user_id)
            )
            await connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка удаления редактора subject {subject_id}, user {user_id}: {e}")
        return False
    finally:
        connection.close()


async def get_topic_redactors(topic_id: int) -> list[dict]:
    connection = await get_connection()
    if connection is None:
        return []

    try:
        async with connection.cursor() as cursor:
            await cursor.execute("""
                SELECT u.id, u.first_name, u.surname, u.patronymic, u.email
                FROM topic_redactors tr
                JOIN users u ON tr.user_id = u.id
                WHERE tr.topic_id = %s
            """, (topic_id,))
            return await cursor.fetchall() or []
    except Exception as e:
        logging.error(f"Ошибка при получении редакторов topic {topic_id}: {e}")
        return []
    finally:
        connection.close()


async def add_topic_redactor(topic_id: int, user_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "INSERT IGNORE INTO topic_redactors (topic_id, user_id) VALUES (%s, %s)",
                (topic_id, user_id)
            )
            await connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка добавления редактора topic {topic_id}, user {user_id}: {e}")
        return False
    finally:
        connection.close()


async def remove_topic_redactor(topic_id: int, user_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM topic_redactors WHERE topic_id = %s AND user_id = %s",
                (topic_id, user_id)
            )
            await connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка удаления редактора topic {topic_id}, user {user_id}: {e}")
        return False
    finally:
        connection.close()


async def is_user_topic_redactor(topic_id: int, user_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "SELECT 1 FROM topic_redactors WHERE topic_id = %s AND user_id = %s",
                (topic_id, user_id)
            )
            result = await cursor.fetchone()
            return result is not None

    except Exception as e:
        import logging
        logging.error(f"Ошибка БД при проверке прав на тему (topic: {topic_id}, user: {user_id}): {e}")
        return False

    finally:
        connection.close()


async def get_task_redactors(task_id: int) -> list[dict]:
    connection = await get_connection()
    if connection is None:
        return []

    try:
        async with connection.cursor() as cursor:
            await cursor.execute("""
                SELECT u.id, u.first_name, u.surname, u.patronymic, u.email
                FROM task_redactors tr
                JOIN users u ON tr.user_id = u.id
                WHERE tr.task_id = %s
            """, (task_id,))
            return await cursor.fetchall() or []
    except Exception as e:
        logging.error(f"Ошибка при получении редакторов task {task_id}: {e}")
        return []
    finally:
        connection.close()


async def add_task_redactor(task_id: int, user_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "INSERT IGNORE INTO task_redactors (task_id, user_id) VALUES (%s, %s)",
                (task_id, user_id)
            )
            await connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка добавления редактора task {task_id}, user {user_id}: {e}")
        return False
    finally:
        connection.close()


async def remove_task_redactor(task_id: int, user_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM task_redactors WHERE task_id = %s AND user_id = %s",
                (task_id, user_id)
            )
            await connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка удаления редактора task {task_id}, user {user_id}: {e}")
        return False
    finally:
        connection.close()


async def is_user_task_redactor(task_id: int, user_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "SELECT 1 FROM task_redactors WHERE task_id = %s AND user_id = %s",
                (task_id, user_id)
            )
            result = await cursor.fetchone()
            return result is not None

    except Exception as e:
        logging.error(f"Ошибка БД при проверке прав на задание (task: {task_id}, user: {user_id}): {e}")
        return False

    finally:
        connection.close()


async def get_subject_students(subject_id: int) -> list[dict]:
    connection = await get_connection()
    if connection is None:
        return []

    try:
        async with connection.cursor() as cursor:
            await cursor.execute("""
                SELECT u.id, u.first_name, u.surname, u.patronymic, u.email,
                       ss.access_all_topics, ss.access_all_tasks
                FROM student_subjects ss
                JOIN users u ON ss.student_id = u.id
                WHERE ss.subject_id = %s
            """, (subject_id,))
            return await cursor.fetchall() or []
    except Exception as e:
        logging.error(f"Ошибка при получении студентов subject {subject_id}: {e}")
        return []
    finally:
        connection.close()


async def add_student_subject(
    student_id: int,
    subject_id: int,
    access_all_topics: bool = False,
    access_all_tasks: bool = False
) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO student_subjects (student_id, subject_id, access_all_topics, access_all_tasks)
                   VALUES (%s, %s, %s, %s)
                   AS new
                   ON DUPLICATE KEY UPDATE access_all_topics = new.access_all_topics, access_all_tasks = new.access_all_tasks""",
                (student_id, subject_id, int(access_all_topics), int(access_all_tasks))
            )

            if access_all_topics or access_all_tasks:
                await cursor.execute("SELECT id FROM topics WHERE subject_id = %s", (subject_id,))
                topic_ids = [row['id'] for row in await cursor.fetchall()]

                for topic_id in topic_ids:
                    await cursor.execute(
                        """INSERT INTO student_topics (student_id, topic_id, access_all_tasks)
                           VALUES (%s, %s, %s)
                           AS new
                           ON DUPLICATE KEY UPDATE access_all_tasks = new.access_all_tasks""",
                        (student_id, topic_id, int(access_all_tasks))
                    )

            await connection.commit()
            return True
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка добавления студента {student_id} в subject {subject_id}: {e}")
        return False
    finally:
        connection.close()


async def remove_student_subject(student_id: int, subject_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT id FROM topics WHERE subject_id = %s", (subject_id,))
            topic_ids = [row['id'] for row in await cursor.fetchall()]

            if topic_ids:
                format_strings = ','.join(['%s'] * len(topic_ids))
                await cursor.execute(
                    f"DELETE FROM student_tasks WHERE student_id = %s AND task_id IN (SELECT id FROM tasks WHERE topic_id IN ({format_strings}))",
                    (student_id, *topic_ids)
                )
                await cursor.execute(
                    f"DELETE FROM student_topics WHERE student_id = %s AND topic_id IN ({format_strings})",
                    (student_id, *topic_ids)
                )

            await cursor.execute(
                "DELETE FROM student_subjects WHERE student_id = %s AND subject_id = %s",
                (student_id, subject_id)
            )
            await connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка удаления студента {student_id} из subject {subject_id}: {e}")
        return False
    finally:
        connection.close()


async def get_topic_students(topic_id: int) -> list[dict]:
    connection = await get_connection()
    if connection is None:
        return []

    try:
        async with connection.cursor() as cursor:
            await cursor.execute("""
                SELECT u.id, u.first_name, u.surname, u.patronymic, u.email,
                       st.access_all_tasks
                FROM student_topics st
                JOIN users u ON st.student_id = u.id
                WHERE st.topic_id = %s
            """, (topic_id,))
            return await cursor.fetchall() or []
    except Exception as e:
        logging.error(f"Ошибка при получении студентов topic {topic_id}: {e}")
        return []
    finally:
        connection.close()


async def add_student_topic(student_id: int, topic_id: int, access_all_tasks: bool = False) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO student_topics (student_id, topic_id, access_all_tasks)
                   VALUES (%s, %s, %s)
                   AS new
                   ON DUPLICATE KEY UPDATE access_all_tasks = new.access_all_tasks""",
                (student_id, topic_id, int(access_all_tasks))
            )

            await cursor.execute("SELECT subject_id FROM topics WHERE id = %s", (topic_id,))
            subject_row = await cursor.fetchone()
            if subject_row:
                await cursor.execute(
                    """INSERT INTO student_subjects (student_id, subject_id)
                       VALUES (%s, %s)
                       AS new
                       ON DUPLICATE KEY UPDATE student_id = new.student_id""",
                    (student_id, subject_row['subject_id'])
                )

            if access_all_tasks:
                await cursor.execute("SELECT id FROM tasks WHERE topic_id = %s", (topic_id,))
                task_ids = [row['id'] for row in await cursor.fetchall()]

                for task_id in task_ids:
                    await cursor.execute(
                        """INSERT IGNORE INTO student_tasks (student_id, task_id)
                           VALUES (%s, %s)""",
                        (student_id, task_id)
                    )

            await connection.commit()
            return True
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка добавления студента {student_id} в topic {topic_id}: {e}")
        return False
    finally:
        connection.close()


async def remove_student_topic(student_id: int, topic_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM student_tasks WHERE student_id = %s AND task_id IN (SELECT id FROM tasks WHERE topic_id = %s)",
                (student_id, topic_id)
            )
            await cursor.execute(
                "DELETE FROM student_topics WHERE student_id = %s AND topic_id = %s",
                (student_id, topic_id)
            )
            await connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка удаления студента {student_id} из topic {topic_id}: {e}")
        return False
    finally:
        connection.close()


async def get_task_students(task_id: int) -> list[dict]:
    connection = await get_connection()
    if connection is None:
        return []

    try:
        async with connection.cursor() as cursor:
            await cursor.execute("""
                SELECT u.id, u.first_name, u.surname, u.patronymic, u.email
                FROM student_tasks st
                JOIN users u ON st.student_id = u.id
                WHERE st.task_id = %s
            """, (task_id,))
            return await cursor.fetchall() or []
    except Exception as e:
        logging.error(f"Ошибка при получении студентов task {task_id}: {e}")
        return []
    finally:
        connection.close()


async def add_student_task(student_id: int, task_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "INSERT IGNORE INTO student_tasks (student_id, task_id) VALUES (%s, %s)",
                (student_id, task_id)
            )

            await cursor.execute("""
                SELECT t.id AS topic_id, tp.subject_id
                FROM tasks t
                JOIN topics tp ON t.topic_id = tp.id
                WHERE t.id = %s
            """, (task_id,))
            row = await cursor.fetchone()
            if row:
                await cursor.execute(
                    """INSERT INTO student_topics (student_id, topic_id)
                       VALUES (%s, %s)
                       AS new
                       ON DUPLICATE KEY UPDATE student_id = new.student_id""",
                    (student_id, row['topic_id'])
                )
                await cursor.execute(
                    """INSERT INTO student_subjects (student_id, subject_id)
                       VALUES (%s, %s)
                       AS new
                       ON DUPLICATE KEY UPDATE student_id = new.student_id""",
                    (student_id, row['subject_id'])
                )

            await connection.commit()
            return True
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка добавления студента {student_id} в task {task_id}: {e}")
        return False
    finally:
        connection.close()


async def remove_student_task(student_id: int, task_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM student_tasks WHERE student_id = %s AND task_id = %s",
                (student_id, task_id)
            )
            await connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка удаления студента {student_id} из task {task_id}: {e}")
        return False
    finally:
        connection.close()


# 1. Редактирование предмета
async def update_subject(subject_id: int, name: str, description: str, is_public: bool) -> bool:
    connection = await get_connection()
    if connection is None:
        return False
    try:
        async with connection.cursor() as cursor:
            sql = "UPDATE subjects SET name = %s, description = %s, is_public = %s WHERE id = %s"
            await cursor.execute(sql, (name, description, int(is_public), subject_id))
            await connection.commit()
            return True
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка обновления предмета {subject_id}: {e}")
        return False
    finally:
        connection.close()


async def delete_subject(subject_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False
    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "SELECT id FROM tasks WHERE topic_id IN (SELECT id FROM topics WHERE subject_id = %s)",
                (subject_id,)
            )
            task_ids = [row['id'] for row in await cursor.fetchall()]

            for task_id in task_ids:
                await _delete_task_file(task_id)

            delete_tasks_sql = """
                DELETE FROM tasks 
                WHERE topic_id IN (SELECT id FROM topics WHERE subject_id = %s)
            """
            await cursor.execute(delete_tasks_sql, (subject_id,))

            delete_topics_sql = "DELETE FROM topics WHERE subject_id = %s"
            await cursor.execute(delete_topics_sql, (subject_id,))

            delete_subject_sql = "DELETE FROM subjects WHERE id = %s"
            await cursor.execute(delete_subject_sql, (subject_id,))

            await connection.commit()
            return True
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка каскадного удаления предмета {subject_id} через Python: {e}")
        return False
    finally:
        connection.close()

# 2. Редактирование темы
async def update_topic(topic_id: int, name: str, description: str, is_public: bool) -> bool:
    connection = await get_connection()
    if connection is None:
        return False
    try:
        async with connection.cursor() as cursor:
            sql = "UPDATE topics SET name = %s, description = %s, is_public = %s WHERE id = %s"
            await cursor.execute(sql, (name, description, int(is_public), topic_id))
            await connection.commit()
            return True
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка обновления темы {topic_id}: {e}")
        return False
    finally:
        connection.close()


async def delete_topic(topic_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT id FROM tasks WHERE topic_id = %s", (topic_id,))
            task_ids = [row['id'] for row in await cursor.fetchall()]

            for task_id in task_ids:
                await _delete_task_file(task_id)

            await cursor.execute("DELETE FROM topics WHERE id = %s", (topic_id,))
            await connection.commit()
            return True
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка удаления темы {topic_id}: {e}")
        return False
    finally:
        connection.close()

# 3. Редактирование задания
async def update_task(
    task_id: int,
    name: str,
    description: str,
    is_public: bool,
    question_type: str = None,
    correct_text: str = None,
    is_case_sensitive: int = 0,
    options: list = None,
    correct_options: list = None,
) -> bool:
    connection = await get_connection()
    if connection is None:
        return False
    try:
        async with connection.cursor() as cursor:
            sql = """
                UPDATE tasks 
                SET name = %s, description = %s, is_public = %s
                WHERE id = %s
            """
            await cursor.execute(sql, (name, description, int(is_public), task_id))

            if question_type:
                await cursor.execute("UPDATE tasks SET question_type = %s WHERE id = %s", (question_type, task_id))
                await cursor.execute("DELETE FROM text_tasks WHERE task_id = %s", (task_id,))
                await cursor.execute("DELETE FROM choice_tasks WHERE task_id = %s", (task_id,))

                if question_type == 'text':
                    await cursor.execute(
                        "INSERT INTO text_tasks (task_id, correct_answer, is_case_sensitive) VALUES (%s, %s, %s)",
                        (task_id, correct_text, is_case_sensitive)
                    )

                elif question_type == 'choice':
                    opts_json = json.dumps(options) if options else '[]'
                    cor_opts_json = json.dumps(correct_options) if correct_options else '[]'
                    multiple = 1 if correct_options and len(correct_options) > 1 else 0
                    await cursor.execute(
                        "INSERT INTO choice_tasks (task_id, options, correct_options, multiple_correct) VALUES (%s, %s, %s, %s)",
                        (task_id, opts_json, cor_opts_json, multiple)
                    )

            await connection.commit()
            return True
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка обновления задания {task_id}: {e}")
        return False
    finally:
        connection.close()


async def update_task_fields(
    task_id: int,
    name: str,
    description: str,
    is_public: bool,
    question_type: str = None,
    correct_text: str = None,
    is_case_sensitive: int = 0,
    options: list = None,
    correct_options: list = None,
    can_retry: bool = None,
    is_material: bool = False,
) -> bool:
    connection = await get_connection()
    if connection is None:
        return False
    try:
        async with connection.cursor() as cursor:
            if question_type:
                can_retry_val = int(can_retry) if can_retry is not None else 0
                await cursor.execute(
                    "UPDATE tasks SET name = %s, description = %s, is_public = %s, question_type = %s, can_retry = %s WHERE id = %s",
                    (name, description, int(is_public), question_type, can_retry_val, task_id)
                )

                await cursor.execute("DELETE FROM choice_tasks WHERE task_id = %s", (task_id,))
                await cursor.execute("DELETE FROM text_tasks WHERE task_id = %s", (task_id,))
                await cursor.execute("DELETE FROM file_tasks WHERE task_id = %s", (task_id,))

                if question_type == 'text':
                    await cursor.execute(
                        "INSERT INTO text_tasks (task_id, correct_answer, is_case_sensitive) VALUES (%s, %s, %s)",
                        (task_id, correct_text, is_case_sensitive)
                    )
                elif question_type == 'choice':
                    opts_json = json.dumps(options) if options else '[]'
                    cor_opts_json = json.dumps(correct_options) if correct_options else '[]'
                    multiple = 1 if correct_options and len(correct_options) > 1 else 0
                    await cursor.execute(
                        "INSERT INTO choice_tasks (task_id, options, correct_options, multiple_correct) VALUES (%s, %s, %s, %s)",
                        (task_id, opts_json, cor_opts_json, multiple)
                    )
                elif question_type == 'file':
                    await cursor.execute(
                        "INSERT INTO file_tasks (task_id, is_material) VALUES (%s, %s)",
                        (task_id, int(is_material))
                    )

                elif question_type == 'material':
                    await cursor.execute(
                        "INSERT INTO file_tasks (task_id, is_material) VALUES (%s, %s)",
                        (task_id, 1)
                    )
            else:
                if can_retry is not None:
                    await cursor.execute(
                        "UPDATE tasks SET name = %s, description = %s, is_public = %s, can_retry = %s WHERE id = %s",
                        (name, description, int(is_public), int(can_retry), task_id)
                    )
                else:
                    await cursor.execute(
                        "UPDATE tasks SET name = %s, description = %s, is_public = %s WHERE id = %s",
                        (name, description, int(is_public), task_id)
                    )

            await connection.commit()
            return True
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка обновления полей задания {task_id}: {e}")
        return False
    finally:
        connection.close()

async def _delete_task_file(task_id: int) -> None:
    connection = await get_connection()
    if connection is None:
        return
    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "SELECT file_path FROM task_attachments WHERE task_id = %s",
                (task_id,)
            )
            attachment_paths = [row['file_path'] for row in await cursor.fetchall()]

            await cursor.execute(
                "SELECT file_path, user_id FROM student_attempts WHERE task_id = %s AND file_path IS NOT NULL",
                (task_id,)
            )
            attempt_rows = await cursor.fetchall()
            student_file_paths = [row['file_path'] for row in attempt_rows]
            student_user_ids = set(row['user_id'] for row in attempt_rows)

        for file_path in attachment_paths + student_file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logging.error(f"Ошибка при удалении файла {file_path}: {e}")

        try:
            task_dir = f"static/uploads/tasks/{task_id}"
            if os.path.exists(task_dir):
                os.rmdir(task_dir)
        except OSError:
            pass

        for uid in student_user_ids:
            try:
                answer_dir = f"static/uploads/student_answers/{uid}/{task_id}"
                if os.path.exists(answer_dir):
                    os.rmdir(answer_dir)
            except OSError:
                pass
    except Exception as e:
        logging.error(f"Ошибка при удалении файлов задания {task_id}: {e}")
    finally:
        connection.close()


async def delete_task(task_id: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False
    try:
        async with connection.cursor() as cursor:
            await _delete_task_file(task_id)
            await cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            await connection.commit()
            return True
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка при удалении задания {task_id} из базы: {e}")
        return False
    finally:
        connection.close()



async def get_task_by_id(task_id: int) -> dict:
    """
    Получает информацию о задании, присоединяя данные из специфичных таблиц
    (choice_tasks, text_tasks, file_tasks) в зависимости от типа.
    """
    connection = await get_connection()  # Замени на свою функцию получения коннекта
    if connection is None:
        return {}

    try:
        # Предполагаем использование DictCursor (возвращает dict)
        async with connection.cursor() as cursor:
            sql = """
                SELECT t.*, 
                       c.options, c.correct_options, c.multiple_correct, c.shuffle_options,
                       txt.correct_answer, txt.is_case_sensitive, txt.max_length,
                       f.max_file_size, f.allowed_types, f.is_material
                FROM tasks t
                LEFT JOIN choice_tasks c ON t.id = c.task_id
                LEFT JOIN text_tasks txt ON t.id = txt.task_id
                LEFT JOIN file_tasks f ON t.id = f.task_id
                WHERE t.id = %s
            """
            await cursor.execute(sql, (task_id,))
            task = await cursor.fetchone()

            if task:
                json_fields = ['options', 'correct_options', 'allowed_types']
                for field in json_fields:
                    if task.get(field) and isinstance(task[field], str):
                        try:
                            task[field] = json.loads(task[field])
                        except json.JSONDecodeError:
                            pass

            return task

    except Exception as e:
        logging.error(f"Ошибка при получении задания {task_id}: {e}")
        return {}
    finally:
        connection.close()


async def save_student_attempt(
    user_id: int,
    task_id: int,
    is_correct: Optional[bool] = None,   # Может быть True, False или None (для файлов)
    answer_text: Optional[str] = None, # Текст ответа или JSON-строка вариантов
    file_path: Optional[str] = None    # Путь к файлу на сервере
) -> bool:
    """
    Сохраняет результат попытки решения в таблицу student_attempts.
    Поддерживает сохранение текстовых ответов и путей к файлам.
    """
    connection = await get_connection()
    if connection is None:
        return False

    try:
        async with connection.cursor() as cursor:
            # Обновленный SQL-запрос с учетом новых колонок
            sql = """
                INSERT INTO student_attempts (user_id, task_id, is_correct, answer_text, file_path)
                VALUES (%s, %s, %s, %s, %s)
            """
            await cursor.execute(sql, (user_id, task_id, is_correct, answer_text, file_path))
            await connection.commit()
            return True

    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка сохранения попытки пользователя {user_id} для задачи {task_id}: {e}")
        return False
    finally:
        connection.close()


async def get_student_attempts(user_id: int, task_ids: list[int]) -> dict[int, Optional[bool]]:
    if not task_ids:
        return {}

    connection = await get_connection()
    if connection is None:
        return {}

    try:
        async with connection.cursor() as cursor:
            format_strings = ','.join(['%s'] * len(task_ids))
            sql = f"""
                SELECT task_id, is_correct
                FROM student_attempts
                WHERE user_id = %s AND task_id IN ({format_strings})
            """
            await cursor.execute(sql, (user_id, *task_ids))
            rows = await cursor.fetchall()

            return {row['task_id']: row['is_correct'] for row in rows} if rows else {}

    except Exception as e:
        logging.error(f"Ошибка при получении попыток пользователя {user_id}: {e}")
        return {}
    finally:
        connection.close()


async def get_task_submissions(task_id: int) -> list[dict]:
    connection = await get_connection()
    if connection is None:
        return []
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("""
                SELECT sa.user_id, sa.file_path, sa.answer_text, sa.is_correct,
                       u.surname, u.first_name, u.patronymic
                FROM student_attempts sa
                JOIN users u ON sa.user_id = u.id
                WHERE sa.task_id = %s AND sa.file_path IS NOT NULL
                ORDER BY sa.is_correct ASC
            """, (task_id,))
            return await cursor.fetchall() or []
    except Exception as e:
        logging.error(f"Ошибка получения файловых submissions {task_id}: {e}")
        return []
    finally:
        connection.close()


async def update_attempt_review(user_id: int, task_id: int, is_correct: int) -> bool:
    connection = await get_connection()
    if connection is None:
        return False
    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "UPDATE student_attempts SET is_correct = %s WHERE user_id = %s AND task_id = %s",
                (is_correct, user_id, task_id)
            )
            await connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        await connection.rollback()
        logging.error(f"Ошибка review попытки user {user_id}, task {task_id}: {e}")
        return False
    finally:
        connection.close()


async def get_submission_file_path(user_id: int, task_id: int) -> str | None:
    connection = await get_connection()
    if connection is None:
        return None
    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "SELECT file_path FROM student_attempts WHERE user_id = %s AND task_id = %s AND file_path IS NOT NULL LIMIT 1",
                (user_id, task_id)
            )
            row = await cursor.fetchone()
            return row['file_path'] if row else None
    except Exception as e:
        logging.error(f"Ошибка получения file_path user {user_id}, task {task_id}: {e}")
        return None
    finally:
        connection.close()


async def get_redactor_subject_ids(subject_ids: list[int], user_id: int) -> set[int]:
    if not subject_ids:
        return set()

    connection = await get_connection()
    if connection is None:
        return set()

    try:
        async with connection.cursor() as cursor:
            format_strings = ','.join(['%s'] * len(subject_ids))
            sql = f"""
                SELECT DISTINCT subject_id FROM subject_redactors
                WHERE subject_id IN ({format_strings}) AND user_id = %s
            """
            await cursor.execute(sql, (*subject_ids, user_id))
            rows = await cursor.fetchall()
            return {row['subject_id'] for row in rows}
    except Exception as e:
        logging.error(f"Ошибка при пакетной проверке прав редактора: {e}")
        return set()
    finally:
        connection.close()