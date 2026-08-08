import logging
from contextlib import asynccontextmanager
from typing import Optional

import json
import os

from dotenv import load_dotenv
from aiomysql import connect, DictCursor
from pydantic import TypeAdapter

from src.config import UPLOADS_DIR
from src.schemas import (
    UserReadSchema, UserBriefSchema, SubjectReadSchema, SubjectStudentReadSchema,
    TopicReadSchema, TopicStudentReadSchema, AttachmentReadSchema,
    TaskReadSchema, TaskSubmissionReadSchema,
)

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "db": os.getenv("DB_NAME"),
}

task_adapter = TypeAdapter(TaskReadSchema)


async def get_connection():
    try:
        return await connect(**DB_CONFIG, cursorclass=DictCursor)
    except Exception as e:
        logging.error(f"Ошибка подключения: {e}")
        return None


class NoConnectionError(Exception):
    pass


class BaseRepository:
    async def _fetchone(self, sql: str, params=()) -> dict | None:
        connection = await get_connection()
        if connection is None:
            return None
        try:
            async with connection.cursor() as cursor:
                await cursor.execute(sql, params)
                return await cursor.fetchone()
        except Exception as e:
            logging.error(f"Ошибка БД в {self.__class__.__name__}: {e}")
            return None
        finally:
            connection.close()

    async def _fetchall(self, sql: str, params=()) -> list:
        connection = await get_connection()
        if connection is None:
            return []
        try:
            async with connection.cursor() as cursor:
                await cursor.execute(sql, params)
                return await cursor.fetchall() or []
        except Exception as e:
            logging.error(f"Ошибка БД в {self.__class__.__name__}: {e}")
            return []
        finally:
            connection.close()

    async def _execute(self, sql: str, params=()) -> int:
        connection = await get_connection()
        if connection is None:
            return -1
        try:
            async with connection.cursor() as cursor:
                await cursor.execute(sql, params)
                await connection.commit()
                return cursor.rowcount
        except Exception as e:
            logging.error(f"Ошибка БД в {self.__class__.__name__}: {e}")
            return -1
        finally:
            connection.close()

    @asynccontextmanager
    async def _transaction(self):
        connection = await get_connection()
        if connection is None:
            raise NoConnectionError()
        try:
            async with connection.cursor() as cursor:
                yield cursor
            await connection.commit()
        except Exception:
            await connection.rollback()
            raise
        finally:
            connection.close()


class UserRepository(BaseRepository):
    async def is_in_users(self, data: dict[str, str]) -> bool:
        row = await self._fetchone(
            "SELECT id FROM users WHERE surname = %s AND first_name = %s AND patronymic = %s AND email = %s",
            (data["surname"], data["name"], data["patronymic"], data["email"]),
        )
        return row is not None

    async def add_new_user(self, data) -> bool:
        return (await self._execute(
            "INSERT INTO users (surname, first_name, patronymic, email, password_hash, is_teacher) VALUES (%s, %s, %s, %s, %s, %s)",
            (data["surname"], data["name"], data["patronymic"], data["email"], data["password_hash"], data["is_teacher"]),
        )) >= 0

    async def get_user_by_email(self, email: str) -> list[UserReadSchema]:
        rows = await self._fetchall("SELECT * FROM users WHERE email = %s", (email,))
        return [UserReadSchema.model_validate(r) for r in rows]

    async def get_user_by_id(self, id: int) -> UserReadSchema | None:
        row = await self._fetchone("SELECT * FROM users WHERE id = %s LIMIT 1", (id,))
        return UserReadSchema.model_validate(row) if row else None

    async def search_users(self, query: str) -> list[UserBriefSchema]:
        words = [w.strip() for w in query.strip().split() if w.strip()][:5]
        if not words:
            return []
        search_terms = ' '.join(f"+{word}*" for word in words)
        sql = """
            SELECT id, first_name, surname, patronymic, email, is_teacher
            FROM users
            WHERE MATCH(first_name, surname, email) AGAINST(%s IN BOOLEAN MODE)
            LIMIT 20
        """
        rows = await self._fetchall(sql, (search_terms,))
        return [UserBriefSchema.model_validate(r) for r in rows]


class SubjectRepository(BaseRepository):
    async def get_all_subjects(self, user_id: int, is_teacher: bool) -> list[SubjectReadSchema]:
        if is_teacher:
            sql = """
                SELECT DISTINCT s.* FROM subjects s
                LEFT JOIN subject_redactors sr ON s.id = sr.subject_id
                WHERE s.created_by = %s
                OR sr.user_id = %s
                OR s.is_public = 1
            """
            rows = await self._fetchall(sql, (user_id, user_id))
        else:
            sql = """
                SELECT DISTINCT s.* FROM subjects s
                LEFT JOIN student_subjects ss ON s.id = ss.subject_id
                WHERE ss.student_id = %s
                OR s.is_public = 1
            """
            rows = await self._fetchall(sql, (user_id,))
        return [SubjectReadSchema.model_validate(r) for r in rows]

    async def get_subject_by_id(self, subject_id: int) -> SubjectReadSchema | None:
        row = await self._fetchone(
            "SELECT id, name, description, created_by, is_public FROM subjects WHERE id = %s",
            (subject_id,),
        )
        return SubjectReadSchema.model_validate(row) if row else None

    async def get_subject_creator(self, subject_id: int) -> int | None:
        subject = await self.get_subject_by_id(subject_id)
        return subject.created_by if subject else None

    async def add_new_subject(self, name: str, description: str, user_id: int, is_public: bool = True) -> dict:
        try:
            async with self._transaction() as cursor:
                await cursor.execute(
                    "INSERT INTO subjects (name, description, created_by, is_public) VALUES (%s, %s, %s, %s)",
                    (name, description, user_id, is_public)
                )
                subject_id = cursor.lastrowid

                await cursor.execute(
                    "INSERT INTO subject_redactors (subject_id, user_id) VALUES (%s, %s)",
                    (subject_id, user_id)
                )

                return {
                    'id': str(subject_id),
                    'name': name,
                    'description': description,
                    'created_by': user_id,
                    'is_public': is_public,
                }
        except Exception as e:
            logging.error(f"Ошибка при создании предмета '{name}': {e}")
            return {}

    async def update_subject(self, subject_id: int, name: str, description: str, is_public: bool) -> bool:
        return (await self._execute(
            "UPDATE subjects SET name = %s, description = %s, is_public = %s WHERE id = %s",
            (name, description, int(is_public), subject_id),
        )) >= 0

    async def delete_subject(self, subject_id: int) -> bool:
        try:
            async with self._transaction() as cursor:
                await cursor.execute(
                    "SELECT id FROM tasks WHERE topic_id IN (SELECT id FROM topics WHERE subject_id = %s)",
                    (subject_id,)
                )
                task_ids = [row['id'] for row in await cursor.fetchall()]

                for task_id in task_ids:
                    await task_repository._delete_task_file(task_id)

                await cursor.execute(
                    "DELETE FROM tasks WHERE topic_id IN (SELECT id FROM topics WHERE subject_id = %s)",
                    (subject_id,)
                )
                await cursor.execute("DELETE FROM topics WHERE subject_id = %s", (subject_id,))
                await cursor.execute("DELETE FROM subjects WHERE id = %s", (subject_id,))

                return True
        except Exception as e:
            logging.error(f"Ошибка каскадного удаления предмета {subject_id} через Python: {e}")
            return False


class TaskRepository(BaseRepository):
    async def get_topic_creator(self, topic_id: int) -> int | None:
        topic = await self.get_topic_by_id(topic_id)
        return topic.created_by if topic else None

    async def get_topics_by_subject_id(
        self, subject_id: int, user_id: int = None, is_teacher: bool = False
    ) -> list[TopicReadSchema]:
        if is_teacher or user_id is None:
            rows = await self._fetchall("SELECT * FROM topics WHERE subject_id = %s", (subject_id,))
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
            rows = await self._fetchall(sql, (user_id, user_id, subject_id))
        return [TopicReadSchema.model_validate(r) for r in rows]

    async def get_tasks_by_topic_id(
        self, topic_id: int, only_public: bool = False, user_id: int = None, is_teacher: bool = False
    ) -> list[TaskReadSchema]:
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

        tasks = await self._fetchall(sql, tuple(params))
        if not tasks:
            return []

        task_ids = [t['id'] for t in tasks]
        format_strings = ','.join(['%s'] * len(task_ids))
        attachments = await self._fetchall(
            f"SELECT * FROM task_attachments WHERE task_id IN ({format_strings})",
            tuple(task_ids),
        )

        json_fields = ['options', 'correct_options', 'allowed_types']
        for task in tasks:
            for field in json_fields:
                if task.get(field) and isinstance(task[field], str):
                    try:
                        task[field] = json.loads(task[field])
                    except json.JSONDecodeError:
                        pass

        try:
            return [
                task_adapter.validate_python({
                    **task,
                    'attachments': [
                        AttachmentReadSchema.model_validate(a)
                        for a in attachments
                        if a['task_id'] == task['id']
                    ],
                })
                for task in tasks
            ]
        except Exception as e:
            logging.error(f"Ошибка при запросе заданий: {e}")
            return []

    async def get_topic_by_id(self, topic_id: int) -> TopicReadSchema | None:
        row = await self._fetchone(
            "SELECT id, name, description, created_by, subject_id, is_public FROM topics WHERE id = %s",
            (topic_id,),
        )
        return TopicReadSchema.model_validate(row) if row else None

    async def add_new_topic(
        self, name: str, description: str, user_id: int, subject_id: int, is_public_input: bool
    ) -> dict:
        try:
            async with self._transaction() as cursor:
                await cursor.execute("SELECT is_public FROM subjects WHERE id = %s", (subject_id,))
                subject = await cursor.fetchone()

                if not subject:
                    logging.warning(f"Попытка добавить тему в несуществующий предмет (ID: {subject_id})")
                    return {}

                final_is_public = 1 if (subject.get('is_public') and is_public_input) else 0

                await cursor.execute(
                    "INSERT INTO topics (name, description, created_by, subject_id, is_public) VALUES (%s, %s, %s, %s, %s)",
                    (name, description, user_id, subject_id, final_is_public)
                )
                topic_id = cursor.lastrowid

                await cursor.execute(
                    "INSERT INTO topic_redactors (topic_id, user_id) VALUES (%s, %s)",
                    (topic_id, user_id)
                )

                return {'id': topic_id, 'is_public': final_is_public}
        except Exception as e:
            logging.error(f"Ошибка при добавлении темы '{name}' к предмету {subject_id}: {e}")
            return {}

    async def add_new_task(
        self,
        topic_id: int,
        name: str,
        description: str,
        user_id: int,
        is_public_input: bool,
        question_type: str,
        correct_text: str = None,
        is_case_sensitive: int = 0,
        options: list = None,
        correct_options: list = None,
        can_retry: bool = False,
        is_material: bool = False,
    ) -> dict:
        try:
            async with self._transaction() as cursor:
                await cursor.execute("SELECT is_public FROM topics WHERE id = %s", (topic_id,))
                topic = await cursor.fetchone()

                if not topic:
                    return {}

                final_is_public = 1 if (topic.get('is_public') and is_public_input) else 0

                await cursor.execute(
                    "INSERT INTO tasks (name, topic_id, description, created_by, is_public, question_type, can_retry) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (name, topic_id, description, user_id, final_is_public, question_type, int(can_retry))
                )
                task_id = cursor.lastrowid

                await self._write_task_details(
                    cursor, task_id, question_type, correct_text, is_case_sensitive,
                    options, correct_options, is_material,
                )

                await cursor.execute(
                    "INSERT INTO task_redactors (task_id, user_id) VALUES (%s, %s)",
                    (task_id, user_id)
                )

                return {'id': task_id, 'is_public': final_is_public}
        except Exception as e:
            logging.error(f"Ошибка при добавлении задания: {e}")
            return {}

    async def add_task_attachment(self, task_id: int, file_path: str, file_name: str):
        await self._execute(
            "INSERT INTO task_attachments (task_id, file_path, file_name) VALUES (%s, %s, %s)",
            (task_id, file_path, file_name),
        )

    async def get_task_attachment(self, attachment_id: int) -> AttachmentReadSchema | None:
        row = await self._fetchone(
            "SELECT * FROM task_attachments WHERE id = %s",
            (attachment_id,),
        )
        return AttachmentReadSchema.model_validate(row) if row else None

    async def update_topic(self, topic_id: int, name: str, description: str, is_public: bool) -> bool:
        return (await self._execute(
            "UPDATE topics SET name = %s, description = %s, is_public = %s WHERE id = %s",
            (name, description, int(is_public), topic_id),
        )) >= 0

    async def delete_topic(self, topic_id: int) -> bool:
        try:
            async with self._transaction() as cursor:
                await cursor.execute("SELECT id FROM tasks WHERE topic_id = %s", (topic_id,))
                task_ids = [row['id'] for row in await cursor.fetchall()]

                for task_id in task_ids:
                    await self._delete_task_file(task_id)

                await cursor.execute("DELETE FROM topics WHERE id = %s", (topic_id,))

                return True
        except Exception as e:
            logging.error(f"Ошибка удаления темы {topic_id}: {e}")
            return False

    async def update_task_fields(
        self,
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
        try:
            async with self._transaction() as cursor:
                if question_type:
                    can_retry_val = int(can_retry) if can_retry is not None else 0
                    await cursor.execute(
                        "UPDATE tasks SET name = %s, description = %s, is_public = %s, question_type = %s, can_retry = %s WHERE id = %s",
                        (name, description, int(is_public), question_type, can_retry_val, task_id)
                    )

                    await cursor.execute("DELETE FROM choice_tasks WHERE task_id = %s", (task_id,))
                    await cursor.execute("DELETE FROM text_tasks WHERE task_id = %s", (task_id,))
                    await cursor.execute("DELETE FROM file_tasks WHERE task_id = %s", (task_id,))

                    await self._write_task_details(
                        cursor, task_id, question_type, correct_text, is_case_sensitive,
                        options, correct_options, is_material,
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

                return True
        except Exception as e:
            logging.error(f"Ошибка обновления полей задания {task_id}: {e}")
            return False

    async def delete_task(self, task_id: int) -> bool:
        try:
            async with self._transaction() as cursor:
                await self._delete_task_file(task_id)
                await cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))

                return True
        except Exception as e:
            logging.error(f"Ошибка при удалении задания {task_id} из базы: {e}")
            return False

    async def get_task_by_id(self, task_id: int) -> TaskReadSchema | None:
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
        task = await self._fetchone(sql, (task_id,))
        if not task:
            return None

        json_fields = ['options', 'correct_options', 'allowed_types']
        for field in json_fields:
            if task.get(field) and isinstance(task[field], str):
                try:
                    task[field] = json.loads(task[field])
                except json.JSONDecodeError:
                    pass

        try:
            return task_adapter.validate_python(task)
        except Exception as e:
            logging.error(f"Ошибка при получении задания {task_id}: {e}")
            return None

    async def _delete_task_file(self, task_id: int) -> None:
        try:
            async with self._transaction() as cursor:
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
                task_dir = UPLOADS_DIR / "tasks" / str(task_id)
                if os.path.exists(task_dir):
                    os.rmdir(task_dir)
            except OSError:
                pass

            for uid in student_user_ids:
                try:
                    answer_dir = UPLOADS_DIR / "student_answers" / str(uid) / str(task_id)
                    if os.path.exists(answer_dir):
                        os.rmdir(answer_dir)
                except OSError:
                    pass
        except Exception as e:
            logging.error(f"Ошибка при удалении файлов задания {task_id}: {e}")

    async def _write_task_details(
        self,
        cursor,
        task_id: int,
        question_type: str,
        correct_text: str = None,
        is_case_sensitive: int = 0,
        options: list = None,
        correct_options: list = None,
        is_material: bool = False,
    ) -> None:
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


class AccessRepository(BaseRepository):
    async def is_user_subject_redactor(self, subject_id: int, user_id: int) -> bool:
        row = await self._fetchone(
            "SELECT 1 FROM subject_redactors WHERE subject_id = %s AND user_id = %s",
            (subject_id, user_id),
        )
        return row is not None

    async def get_subject_redactors(self, subject_id: int) -> list[UserBriefSchema]:
        rows = await self._fetchall("""
            SELECT u.id, u.first_name, u.surname, u.patronymic, u.email
            FROM subject_redactors sr
            JOIN users u ON sr.user_id = u.id
            WHERE sr.subject_id = %s
        """, (subject_id,))
        return [UserBriefSchema.model_validate(r) for r in rows]

    async def add_subject_redactor(self, subject_id: int, user_id: int) -> bool:
        return (await self._execute(
            "INSERT IGNORE INTO subject_redactors (subject_id, user_id) VALUES (%s, %s)",
            (subject_id, user_id),
        )) > 0

    async def remove_subject_redactor(self, subject_id: int, user_id: int) -> bool:
        return (await self._execute(
            "DELETE FROM subject_redactors WHERE subject_id = %s AND user_id = %s",
            (subject_id, user_id),
        )) > 0

    async def get_topic_redactors(self, topic_id: int) -> list[UserBriefSchema]:
        rows = await self._fetchall("""
            SELECT u.id, u.first_name, u.surname, u.patronymic, u.email
            FROM topic_redactors tr
            JOIN users u ON tr.user_id = u.id
            WHERE tr.topic_id = %s
        """, (topic_id,))
        return [UserBriefSchema.model_validate(r) for r in rows]

    async def add_topic_redactor(self, topic_id: int, user_id: int) -> bool:
        return (await self._execute(
            "INSERT IGNORE INTO topic_redactors (topic_id, user_id) VALUES (%s, %s)",
            (topic_id, user_id),
        )) > 0

    async def remove_topic_redactor(self, topic_id: int, user_id: int) -> bool:
        return (await self._execute(
            "DELETE FROM topic_redactors WHERE topic_id = %s AND user_id = %s",
            (topic_id, user_id),
        )) > 0

    async def is_user_topic_redactor(self, topic_id: int, user_id: int) -> bool:
        row = await self._fetchone(
            "SELECT 1 FROM topic_redactors WHERE topic_id = %s AND user_id = %s",
            (topic_id, user_id),
        )
        return row is not None

    async def get_task_redactors(self, task_id: int) -> list[UserBriefSchema]:
        rows = await self._fetchall("""
            SELECT u.id, u.first_name, u.surname, u.patronymic, u.email
            FROM task_redactors tr
            JOIN users u ON tr.user_id = u.id
            WHERE tr.task_id = %s
        """, (task_id,))
        return [UserBriefSchema.model_validate(r) for r in rows]

    async def add_task_redactor(self, task_id: int, user_id: int) -> bool:
        return (await self._execute(
            "INSERT IGNORE INTO task_redactors (task_id, user_id) VALUES (%s, %s)",
            (task_id, user_id),
        )) > 0

    async def remove_task_redactor(self, task_id: int, user_id: int) -> bool:
        return (await self._execute(
            "DELETE FROM task_redactors WHERE task_id = %s AND user_id = %s",
            (task_id, user_id),
        )) > 0

    async def is_user_task_redactor(self, task_id: int, user_id: int) -> bool:
        row = await self._fetchone(
            "SELECT 1 FROM task_redactors WHERE task_id = %s AND user_id = %s",
            (task_id, user_id),
        )
        return row is not None

    async def get_subject_students(self, subject_id: int) -> list[SubjectStudentReadSchema]:
        rows = await self._fetchall("""
            SELECT u.id, u.first_name, u.surname, u.patronymic, u.email,
                   ss.access_all_topics, ss.access_all_tasks
            FROM student_subjects ss
            JOIN users u ON ss.student_id = u.id
            WHERE ss.subject_id = %s
        """, (subject_id,))
        return [SubjectStudentReadSchema.model_validate(r) for r in rows]

    async def add_student_subject(
        self,
        student_id: int,
        subject_id: int,
        access_all_topics: bool = False,
        access_all_tasks: bool = False,
    ) -> bool:
        try:
            async with self._transaction() as cursor:
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

                return True
        except Exception as e:
            logging.error(f"Ошибка добавления студента {student_id} в subject {subject_id}: {e}")
            return False

    async def remove_student_subject(self, student_id: int, subject_id: int) -> bool:
        try:
            async with self._transaction() as cursor:
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

                return (await cursor.execute(
                    "DELETE FROM student_subjects WHERE student_id = %s AND subject_id = %s",
                    (student_id, subject_id)
                )) > 0
        except Exception as e:
            logging.error(f"Ошибка удаления студента {student_id} из subject {subject_id}: {e}")
            return False

    async def get_topic_students(self, topic_id: int) -> list[TopicStudentReadSchema]:
        rows = await self._fetchall("""
            SELECT u.id, u.first_name, u.surname, u.patronymic, u.email,
                   st.access_all_tasks
            FROM student_topics st
            JOIN users u ON st.student_id = u.id
            WHERE st.topic_id = %s
        """, (topic_id,))
        return [TopicStudentReadSchema.model_validate(r) for r in rows]

    async def add_student_topic(self, student_id: int, topic_id: int, access_all_tasks: bool = False) -> bool:
        try:
            async with self._transaction() as cursor:
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

                return True
        except Exception as e:
            logging.error(f"Ошибка добавления студента {student_id} в topic {topic_id}: {e}")
            return False

    async def remove_student_topic(self, student_id: int, topic_id: int) -> bool:
        try:
            async with self._transaction() as cursor:
                await cursor.execute(
                    "DELETE FROM student_tasks WHERE student_id = %s AND task_id IN (SELECT id FROM tasks WHERE topic_id = %s)",
                    (student_id, topic_id)
                )
                return (await cursor.execute(
                    "DELETE FROM student_topics WHERE student_id = %s AND topic_id = %s",
                    (student_id, topic_id)
                )) > 0
        except Exception as e:
            logging.error(f"Ошибка удаления студента {student_id} из topic {topic_id}: {e}")
            return False

    async def get_task_students(self, task_id: int) -> list[UserBriefSchema]:
        rows = await self._fetchall("""
            SELECT u.id, u.first_name, u.surname, u.patronymic, u.email
            FROM student_tasks st
            JOIN users u ON st.student_id = u.id
            WHERE st.task_id = %s
        """, (task_id,))
        return [UserBriefSchema.model_validate(r) for r in rows]

    async def add_student_task(self, student_id: int, task_id: int) -> bool:
        try:
            async with self._transaction() as cursor:
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

                return True
        except Exception as e:
            logging.error(f"Ошибка добавления студента {student_id} в task {task_id}: {e}")
            return False

    async def remove_student_task(self, student_id: int, task_id: int) -> bool:
        return (await self._execute(
            "DELETE FROM student_tasks WHERE student_id = %s AND task_id = %s",
            (student_id, task_id),
        )) > 0

    async def get_redactor_subject_ids(self, subject_ids: list[int], user_id: int) -> set[int]:
        if not subject_ids:
            return set()

        format_strings = ','.join(['%s'] * len(subject_ids))
        sql = f"""
            SELECT DISTINCT subject_id FROM subject_redactors
            WHERE subject_id IN ({format_strings}) AND user_id = %s
        """
        rows = await self._fetchall(sql, (*subject_ids, user_id))
        return {row['subject_id'] for row in rows}


class AttemptRepository(BaseRepository):
    async def save_student_attempt(
        self,
        user_id: int,
        task_id: int,
        is_correct: Optional[bool] = None,
        answer_text: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> bool:
        return (await self._execute(
            "INSERT INTO student_attempts (user_id, task_id, is_correct, answer_text, file_path) VALUES (%s, %s, %s, %s, %s)",
            (user_id, task_id, is_correct, answer_text, file_path),
        )) >= 0

    async def get_student_attempts(self, user_id: int, task_ids: list[int]) -> dict[int, Optional[bool]]:
        if not task_ids:
            return {}

        format_strings = ','.join(['%s'] * len(task_ids))
        sql = f"""
            SELECT task_id, is_correct
            FROM student_attempts
            WHERE user_id = %s AND task_id IN ({format_strings})
        """
        rows = await self._fetchall(sql, (user_id, *task_ids))

        return {
            row['task_id']: (
                row['is_correct'] if row['is_correct'] is None
                else bool(row['is_correct'])
            )
            for row in rows
        }

    async def get_task_submissions(self, task_id: int) -> list[TaskSubmissionReadSchema]:
        rows = await self._fetchall("""
            SELECT sa.user_id, sa.file_path, sa.answer_text, sa.is_correct,
                   u.surname, u.first_name, u.patronymic
            FROM student_attempts sa
            JOIN users u ON sa.user_id = u.id
            WHERE sa.task_id = %s AND sa.file_path IS NOT NULL
            ORDER BY sa.is_correct ASC
        """, (task_id,))
        return [TaskSubmissionReadSchema.model_validate(r) for r in rows]

    async def update_attempt_review(self, user_id: int, task_id: int, is_correct: int) -> bool:
        return (await self._execute(
            "UPDATE student_attempts SET is_correct = %s WHERE user_id = %s AND task_id = %s",
            (is_correct, user_id, task_id),
        )) > 0

    async def get_submission_file_path(self, user_id: int, task_id: int) -> str | None:
        row = await self._fetchone(
            "SELECT file_path FROM student_attempts WHERE user_id = %s AND task_id = %s AND file_path IS NOT NULL LIMIT 1",
            (user_id, task_id),
        )
        return row['file_path'] if row else None


user_repository = UserRepository()
subject_repository = SubjectRepository()
task_repository = TaskRepository()
access_repository = AccessRepository()
attempt_repository = AttemptRepository()
