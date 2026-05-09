from mysql.connector import connect
import os
from dotenv import load_dotenv

def get_connection():
    load_dotenv()
    host=os.getenv("DB_HOST")
    user=os.getenv("DB_USER")
    password=os.getenv("DB_PASSWORD")
    db=os.getenv("DB_NAME")
    try:
        connection = connect(
            host=host,
            user=user,
            password=password,
            database=db,
        )

        return connection
    except Exception as e:
        print(f"Ошибка подключения: {e}")
        return None

def get_all_subjects():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM subjects")

    subjects=cursor.fetchall()

    cursor.close()
    connection.close()

    return subjects

def get_subject_by_id(subject_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT name, description FROM subjects WHERE id = %s", (subject_id, ))

    subject = cursor.fetchone()

    cursor.close()
    connection.close()

    return subject

def get_topics_by_subject_id(subject_id):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT id, name FROM topics WHERE subject_id = %s", (subject_id,))

    topics = cursor.fetchall()

    cursor.close()
    connection.close()

    return topics

def get_tasks_by_topic_id(topic_id):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT id, name FROM tasks WHERE topic_id = %s", (topic_id,))

    tasks = cursor.fetchall()

    cursor.close()
    connection.close()

    return tasks

def get_subject_by_topic_id(topic_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT subject_id FROM topics WHERE id = %s", (topic_id, ))

    subject_id = cursor.fetchone()

    cursor.close()
    connection.close()

    return subject_id

def get_topic_by_id(topic_id):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT name FROM topics WHERE id = %s", (topic_id,))

    topic = cursor.fetchone()

    cursor.close()
    connection.close()

    return topic

def is_in_users(data: dict[str: str]) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT id FROM users WHERE surname = %s AND first_name = %s AND patronymic = %s AND email = %s",
                   (data["surname"], data["name"], data["patronymic"], data["email"]))

    answer = cursor.fetchone()

    cursor.close()
    connection.close()


    return True if answer else False

def add_new_user(data):
    connection = get_connection()
    cursor = connection.cursor()
    # print(data)

    cursor.execute("INSERT INTO users (surname, first_name, patronymic, email, password_hash, is_teacher) VALUES"
                   "(%s, %s, %s, %s, %s, %s)",
                   (data["surname"], data["name"], data["patronymic"], data["email"], data["password_hash"], data["is_teacher"]))

    connection.commit()

    cursor.close()
    connection.close()

def get_user_by_email(email: str):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE email = %s",
                   (email,))

    answer = cursor.fetchall()

    cursor.close()
    connection.close()
    return answer

def get_user_by_id(id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE id = %s LIMIT 1",
                   (id,))

    answer = cursor.fetchone()

    cursor.close()
    connection.close()
    return answer


# def get_subject_id_by_subject_name(subject_name):
