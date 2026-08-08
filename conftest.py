import asyncio
import hashlib
import os

import pytest
from dotenv import load_dotenv
from aiomysql import connect, DictCursor
from werkzeug.security import generate_password_hash

load_dotenv()

TEST_DB_NAME = "exam_teacher_test"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _connect(db):
    return connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        db=db,
        cursorclass=DictCursor,
    )


async def _drop_and_create_database(conn):
    cursor = await conn.cursor()
    await cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
    await cursor.execute(
        f"CREATE DATABASE {TEST_DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    await cursor.close()
    await conn.commit()


async def _copy_schema(source_conn, target_conn):
    source_cursor = await source_conn.cursor()
    await source_cursor.execute("SHOW TABLES")
    tables = [list(row.values())[0] for row in await source_cursor.fetchall()]
    await source_cursor.close()

    target_cursor = await target_conn.cursor()
    await target_cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table in tables:
        source_cursor = await source_conn.cursor()
        await source_cursor.execute(f"SHOW CREATE TABLE `{table}`")
        row = await source_cursor.fetchone()
        await source_cursor.close()
        await target_cursor.execute(row["Create Table"])
    await target_cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    await target_cursor.close()
    await target_conn.commit()


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
    source = await _connect(os.getenv("DB_NAME"))
    try:
        await _drop_and_create_database(source)
        target = await _connect(TEST_DB_NAME)
        try:
            await _copy_schema(source, target)
            await _seed(target)
        finally:
            target.close()
    finally:
        source.close()


async def _teardown():
    conn = await _connect(os.getenv("DB_NAME"))
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
