import logging

from aiomysql import connect, DictCursor
import os
from dotenv import load_dotenv

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
        print(f"Ошибка подключения: {e}")
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
        print(f"Ошибка при запросе предметов: {e}")
        return []
    finally:
        connection.close()


async def get_subject_by_id(subject_id: int):
    connection = await get_connection()

    if connection is None:
        return []
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT name, description FROM subjects WHERE id = %s", (subject_id, ))
            return await cursor.fetchone()
    except Exception as e:
        print(f"Ошибка при запросе предметов: {e}")
        return []
    finally:
        connection.close()



async def get_topics_by_subject_id(subject_id):
    connection = await get_connection()

    if connection is None:
        return []
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT * FROM topics WHERE subject_id = %s", (subject_id,))
            return await cursor.fetchall()
    except Exception as e:
        print(f"Ошибка при запросе предметов: {e}")
        return []
    finally:
        connection.close()

async def get_tasks_by_topic_id(topic_id: int, only_public: bool = False):
    connection = await get_connection()
    try:
        async with connection.cursor() as cursor:
            sql = "SELECT * FROM tasks WHERE topic_id = %s"

            if only_public:
                sql += " AND is_public = 1"

            await cursor.execute(sql, (topic_id,))
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

            return tasks
    except Exception as e:
        print(f"Ошибка при запросе предметов: {e}")
        return []
    finally:
        connection.close()

async def get_topic_by_id(topic_id):
    connection = await get_connection()

    if connection is None:
        return []
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT name FROM topics WHERE id = %s", (topic_id,))
            return await cursor.fetchone()
    except Exception as e:
        print(f"Ошибка при запросе предметов: {e}")
        return []
    finally:
        connection.close()

async def is_in_users(data: dict[str: str]) -> bool:
    connection = await get_connection()

    if connection is None:
        return False
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT id FROM users WHERE surname = %s AND first_name = %s AND patronymic = %s AND email = %s",
                                 (data["surname"], data["name"], data["patronymic"], data["email"]))
            return True if await cursor.fetchone() else False
    except Exception as e:
        print(f"Ошибка при запросе предметов: {e}")
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
        print(f"Ошибка при запросе предметов: {e}")
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
        print(f"Ошибка при запросе предметов: {e}")
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
        print(f"Ошибка при запросе предметов: {e}")
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

async def add_new_task(topic_id: int, description: str, user_id: int, is_public_input: bool) -> dict:
    connection = await get_connection()
    if connection is None:
        logging.error("Не удалось получить подключение к БД в add_new_task")
        return {}

    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT is_public FROM topics WHERE id = %s", (topic_id,))
            topic = await cursor.fetchone()

            if not topic:
                logging.warning(f"Попытка добавить задание в несуществующую тему (ID: {topic_id})")
                return {}

            topic_is_public = topic.get('is_public') if topic else 0
            final_is_public = 1 if (topic_is_public and is_public_input) else 0

            sql = """
                INSERT INTO tasks (topic_id, description, created_by, is_public) 
                VALUES (%s, %s, %s, %s)
            """
            await cursor.execute(sql, (topic_id, description, user_id, final_is_public))
            task_id = cursor.lastrowid

            await cursor.execute(
                "INSERT INTO task_redactors (task_id, user_id) VALUES (%s, %s)",
                (task_id, user_id)
            )

            await connection.commit()

            return {'id': task_id, 'is_public': final_is_public}

    except Exception as e:
        # Откатываем любые изменения, если что-то пошло не так
        await connection.rollback()
        logging.error(f"Ошибка при добавлении задания в тему {topic_id}: {e}")
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