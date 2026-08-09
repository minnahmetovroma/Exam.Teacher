import asyncio
import hashlib
import os
import ssl

import pytest
from dotenv import load_dotenv
from aiomysql import connect, DictCursor
from werkzeug.security import generate_password_hash

load_dotenv()

TEST_DB_NAME = "exam_teacher_test"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _connect(db):
    kwargs = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "db": db,
        "cursorclass": DictCursor,
    }
    if os.getenv("DB_SSL", "0").lower() in ("1", "true", "yes", "on"):
        kwargs["ssl"] = ssl.create_default_context(cafile=os.getenv("DB_SSL_CA") or None)
    return connect(**kwargs)


async def _drop_and_create_database(conn):
    cursor = await conn.cursor()
    await cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
    await cursor.execute(
        f"CREATE DATABASE {TEST_DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    await cursor.close()
    await conn.commit()


async def _apply_schema_file(conn):
    with open("schema.sql", encoding="utf-8") as f:
        statements = f.read().split(";\n")
    cursor = await conn.cursor()
    for statement in statements:
        statement = statement.strip()
        if statement:
            await cursor.execute(statement)
    await cursor.close()
    await conn.commit()


async def _seed(conn):
    cursor = await conn.cursor()
    await cursor.execute(
        "INSERT INTO users (id, surname, first_name, patronymic, email, password_hash, is_teacher) "
        "VALUES (1, 'Seed', 'Seed', 'Seed', 'test@example.com', %s, 1)",
        (generate_password_hash(_sha256("test@example.com:password")),),
    )
    await cursor.execute(
        "INSERT INTO users (id, surname, first_name, patronymic, email, password_hash, is_teacher) "
        "VALUES (2, 'Student', 'Test', 'S', 'student@example.com', 'x', 0)"
    )
    await cursor.execute(
        "INSERT INTO users (id, surname, first_name, patronymic, email, password_hash, is_teacher) "
        "VALUES (3, 'Teacher', 'Second', 'T', 'teacher@example.com', 'x', 1)"
    )
    await cursor.execute(
        "INSERT INTO subjects (id, name, description, created_by, is_public) "
        "VALUES (11, 'Seed subject', '', 1, 1)"
    )
    await cursor.execute(
        "INSERT INTO topics (id, name, description, created_by, subject_id, is_public) "
        "VALUES (1, 'Seed topic', '', 1, 11, 1)"
    )
    await cursor.execute(
        "INSERT INTO subject_redactors (subject_id, user_id) VALUES (11, 1)"
    )
    await cursor.execute(
        "INSERT INTO topic_redactors (topic_id, user_id) VALUES (1, 1)"
    )
    await cursor.execute(
        "INSERT INTO student_subjects (student_id, subject_id, access_all_topics, access_all_tasks) "
        "VALUES (2, 11, 1, 1)"
    )
    await cursor.close()
    await conn.commit()


async def _setup():
    conn = await _connect(None)
    try:
        await _drop_and_create_database(conn)
        target = await _connect(TEST_DB_NAME)
        try:
            await _apply_schema_file(target)
            await _seed(target)
        finally:
            target.close()
    finally:
        conn.close()


async def _teardown():
    conn = await _connect(None)
    try:
        cursor = await conn.cursor()
        await cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        await cursor.close()
        await conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="session", autouse=True)
def _isolated_database():
    asyncio.run(_setup())
    os.environ["DB_NAME"] = TEST_DB_NAME
    try:
        yield
    finally:
        os.environ.pop("DB_NAME", None)
        asyncio.run(_teardown())
