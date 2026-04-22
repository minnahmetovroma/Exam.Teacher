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
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM subjects")

    subjects=cursor.fetchall()

    cursor.close()
    connection.close()

    return subjects

def get_subject_by_id(subject_id: int):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT name, description FROM subjects WHERE id = %s", (subject_id, ))

    subject = cursor.fetchall()

    cursor.close()
    connection.close()

    return subject

def get_topics_by_subject_id(subject_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT id, name FROM topics WHERE subject_id = %s", (subject_id,))

    topics = cursor.fetchall()

    cursor.close()
    connection.close()

    return topics

def get_tasks_by_topic_id(topic_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT title FROM tasks WHERE topic_id = %s", (topic_id,))

    tasks = cursor.fetchall()

    cursor.close()
    connection.close()

    return tasks

def get_subject_by_topic_id(topic_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT subject_id FROM topics WHERE id = %s", (topic_id, ))

    subject_id = cursor.fetchall()

    cursor.close()
    connection.close()

    return subject_id

def get_topic_by_id(topic_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT name FROM topics WHERE id = %s", (topic_id,))

    topic = cursor.fetchall()

    cursor.close()
    connection.close()

    return topic

# def get_subject_id_by_subject_name(subject_name):
