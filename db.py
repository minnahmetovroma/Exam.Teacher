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

async def get_all_subjects():
    connection = await get_connection()

    if connection is None:
        return []
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT * FROM subjects")
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
            await cursor.execute("SELECT id, name FROM topics WHERE subject_id = %s", (subject_id,))
            return await cursor.fetchall()
    except Exception as e:
        print(f"Ошибка при запросе предметов: {e}")
        return []
    finally:
        connection.close()

async def get_tasks_by_topic_id(topic_id):
    connection = await get_connection()

    if connection is None:
        return []
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT id, name FROM tasks WHERE topic_id = %s", (topic_id,))
            return await cursor.fetchall()
    except Exception as e:
        print(f"Ошибка при запросе предметов: {e}")
        return []
    finally:
        connection.close()

async def get_subject_by_topic_id(topic_id):
    connection = await get_connection()

    if connection is None:
        return []
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT subject_id FROM topics WHERE id = %s", (topic_id, ))
            return await cursor.fetchone()
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

async def add_new_subject(name: str, description: str, user_id: int):
    connection = await get_connection()

    if connection is None:
        return {}
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("INSERT INTO subjects (name, description, created_by) VALUES (%s, %s, %s)", (name, description, user_id))
            subject_id = cursor.lastrowid
            await cursor.execute("INSERT INTO subject_redactors (subject_id, user_id) VALUES (%s, %s)", (subject_id, user_id))
            await connection.commit()
            return {
                'id': str(subject_id),
                'name': name,
                'description': description,
                'created_by': user_id
            }
    except Exception as e:
        await connection.rollback()
        print(f"Ошибка при запросе предметов: {e}")
        return {}
    finally:
        connection.close()

async def add_new_topic(name: str, description: str, user_id: int, subject_id: int):
    connection = await get_connection()

    if connection is None:
        return {}
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("INSERT INTO topics (name, description, created_by, subject_id) VALUES (%s, %s, %s, %s)", (name, description, user_id, subject_id))
            topic_id = cursor.lastrowid
            await cursor.execute("INSERT INTO topic_redactors (topic_id, user_id) VALUES (%s, %s)", (topic_id, user_id))
            await connection.commit()
            return {
                'id': str(topic_id),
                'name': name,
                'description': description,
                'created_by': user_id,
                "subject_id": str(subject_id)
            }
    except Exception as e:
        await connection.rollback()
        print(f"Ошибка при запросе тем: {e}")
        return {}
    finally:
        connection.close()

# def get_subject_id_by_subject_name(subject_name):
