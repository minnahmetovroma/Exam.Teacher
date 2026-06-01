import asyncio

import pytest


def _run(coro):
    return asyncio.run(coro)


class TestConnection:
    def test_get_connection_returns_valid_connection(self):
        from db import get_connection

        async def verify():
            conn = await get_connection()
            assert conn is not None
            conn.close()

        _run(verify())

    def test_get_connection_uses_dictcursor(self):
        from db import get_connection

        async def verify():
            conn = await get_connection()
            assert conn is not None
            cur = await conn.cursor()
            await cur.execute("SELECT 1 AS v")
            row = await cur.fetchone()
            assert isinstance(row, dict)
            assert row["v"] == 1
            await cur.close()
            conn.close()

        _run(verify())


class TestSubjects:
    def test_get_subject_by_id_returns_dict_for_existing(self):
        from db import get_subject_by_id
        result = _run(get_subject_by_id(11))
        assert isinstance(result, (dict, list))

    def test_get_subject_by_id_returns_none_for_missing(self):
        from db import get_subject_by_id
        result = _run(get_subject_by_id(-1))
        assert result is None

    def test_get_all_subjects_returns_list(self):
        from db import get_all_subjects
        result = _run(get_all_subjects(user_id=1, is_teacher=True))
        assert isinstance(result, list)

    def test_get_topics_by_subject_id_returns_list(self):
        from db import get_topics_by_subject_id
        result = _run(get_topics_by_subject_id(11))
        assert isinstance(result, list)

    def test_get_topics_by_subject_id_returns_list_for_missing(self):
        from db import get_topics_by_subject_id
        result = _run(get_topics_by_subject_id(-1))
        assert isinstance(result, (list, tuple))
        assert len(result) == 0

    def test_create_and_delete_subject(self):
        from db import add_new_subject, get_subject_by_id, delete_subject
        created = _run(add_new_subject(
            name="__test_subject",
            description="temporary",
            user_id=1,
            is_public=True,
        ))
        assert isinstance(created, dict)
        assert "id" in created
        assert created["name"] == "__test_subject"

        fetched = _run(get_subject_by_id(int(created["id"])))
        assert isinstance(fetched, dict)
        assert fetched["name"] == "__test_subject"

        deleted = _run(delete_subject(int(created["id"])))
        assert deleted is True

    def test_create_subject_returns_empty_on_db_error(self):
        from db import add_new_subject
        result = _run(add_new_subject(
            name=None,
            description=None,
            user_id=999999,
            is_public=True,
        ))
        assert result == {}

    def test_update_subject(self):
        from db import add_new_subject, update_subject, get_subject_by_id, \
            delete_subject
        created = _run(add_new_subject(
            name="__test_update", description="before",
            user_id=1, is_public=True,
        ))
        assert created

        ok = _run(update_subject(
            subject_id=int(created["id"]),
            name="__test_updated",
            description="after",
            is_public=False,
        ))
        assert ok is True

        fetched = _run(get_subject_by_id(int(created["id"])))
        assert fetched["name"] == "__test_updated"

        _run(delete_subject(int(created["id"])))

    def test_delete_nonexistent_subject_returns_true(self):
        from db import delete_subject
        assert _run(delete_subject(-1)) is True


class TestTopics:
    def test_get_topic_by_id_returns_none_for_missing(self):
        from db import get_topic_by_id
        result = _run(get_topic_by_id(-1))
        assert result is None

    def test_create_topic_returns_dict(self):
        from db import add_new_topic, delete_topic
        result = _run(add_new_topic(
            name="__test_topic",
            description="temp",
            user_id=1,
            subject_id=11,
            is_public_input=True,
        ))
        assert isinstance(result, dict)
        if result:
            _run(delete_topic(result["id"]))

    def test_create_topic_returns_empty_for_missing_subject(self):
        from db import add_new_topic
        result = _run(add_new_topic(
            name="__test_topic",
            description="temp",
            user_id=1,
            subject_id=-1,
            is_public_input=True,
        ))
        assert result == {}

    def test_update_topic(self):
        from db import add_new_topic, update_topic, delete_topic
        created = _run(add_new_topic(
            name="__test_topic_upd", description="before", user_id=1,
            subject_id=11, is_public_input=True,
        ))
        if not created:
            pytest.skip("could not create test topic")

        ok = _run(update_topic(created["id"], "__test_topic_upd2", "after", False))
        assert ok is True

        _run(delete_topic(created["id"]))

    def test_delete_nonexistent_topic_returns_true(self):
        from db import delete_topic
        assert _run(delete_topic(-1)) is True


class TestTasks:
    def test_get_tasks_by_topic_id_returns_list(self):
        from db import get_tasks_by_topic_id
        result = _run(get_tasks_by_topic_id(1))
        assert isinstance(result, list)

    def test_get_tasks_by_topic_id_public_only(self):
        from db import get_tasks_by_topic_id
        result = _run(get_tasks_by_topic_id(1, only_public=True))
        assert isinstance(result, list)

    def test_get_tasks_by_topic_id_returns_empty_for_missing(self):
        from db import get_tasks_by_topic_id
        result = _run(get_tasks_by_topic_id(-1))
        assert result == []

    def test_create_task_text(self):
        from db import add_new_task, delete_task
        result = _run(add_new_task(
            topic_id=1,
            name="__test_task_text",
            description="text task",
            user_id=1,
            is_public_input=True,
            question_type="text",
            correct_text="expected answer",
            is_case_sensitive=0,
        ))
        assert isinstance(result, dict)
        if result:
            _run(delete_task(result["id"]))

    def test_create_task_choice(self):
        from db import add_new_task, delete_task
        result = _run(add_new_task(
            topic_id=1,
            name="__test_task_choice",
            description="choice task",
            user_id=1,
            is_public_input=True,
            question_type="choice",
            options=["A", "B", "C"],
            correct_options=["0"],
        ))
        assert isinstance(result, dict)
        if result:
            _run(delete_task(result["id"]))

    def test_create_task_file(self):
        from db import add_new_task, delete_task
        result = _run(add_new_task(
            topic_id=1,
            name="__test_task_file",
            description="file task",
            user_id=1,
            is_public_input=True,
            question_type="file",
        ))
        assert isinstance(result, dict)
        if result:
            _run(delete_task(result["id"]))

    def test_create_task_returns_empty_for_missing_topic(self):
        from db import add_new_task
        result = _run(add_new_task(
            topic_id=-1,
            name="__test_task",
            description="",
            user_id=1,
            is_public_input=True,
            question_type="text",
        ))
        assert result == {}

    def test_update_task(self):
        from db import add_new_task, update_task, delete_task
        created = _run(add_new_task(
            topic_id=1, name="__test_task_upd", description="before",
            user_id=1, is_public_input=True, question_type="text",
        ))
        if not created:
            pytest.skip("could not create test task")

        ok = _run(update_task(created["id"], "__test_task_upd2", "after", False))
        assert ok is True

        _run(delete_task(created["id"]))

    def test_delete_nonexistent_task_returns_true(self):
        from db import delete_task
        assert _run(delete_task(-1)) is True

    def test_get_task_by_id_returns_none_for_missing(self):
        from db import get_task_by_id
        result = _run(get_task_by_id(-1))
        assert result is None

    def test_get_task_by_id_parses_json_fields(self):
        from db import add_new_task, get_task_by_id, delete_task
        created = _run(add_new_task(
            topic_id=1, name="__test_json", description="",
            user_id=1, is_public_input=True, question_type="choice",
            options=["X", "Y"], correct_options=["0"],
        ))
        if not created:
            pytest.skip("could not create test task")

        task = _run(get_task_by_id(created["id"]))
        if task:
            assert isinstance(task["options"], list)
            assert isinstance(task["correct_options"], list)

        _run(delete_task(created["id"]))


class TestUsers:
    def test_get_user_by_id_returns_dict_or_none(self):
        from db import get_user_by_id
        result = _run(get_user_by_id(1))
        assert isinstance(result, (dict, type(None)))

    def test_get_user_by_id_returns_none_for_missing(self):
        from db import get_user_by_id
        assert _run(get_user_by_id(-1)) is None

    def test_get_user_by_email_returns_tuple(self):
        from db import get_user_by_email
        result = _run(get_user_by_email("test@example.com"))
        assert isinstance(result, (tuple, list))

    def test_get_user_by_email_returns_empty_for_missing(self):
        from db import get_user_by_email
        result = _run(get_user_by_email("nonexistent@example.com"))
        assert result == ()

    def test_is_in_users_returns_bool(self):
        from db import is_in_users
        data = {
            "surname": "", "name": "", "patronymic": "", "email": "",
        }
        result = _run(is_in_users(data))
        assert isinstance(result, bool)

    def test_add_new_user_and_cleanup(self):
        from db import add_new_user, get_user_by_email, is_in_users
        email = "__test@cleanup.local"
        data = {
            "surname": "Test", "name": "User", "patronymic": "Agent",
            "email": email, "password_hash": "hash", "is_teacher": 1,
        }
        already_exists = _run(is_in_users(data))
        if not already_exists:
            _run(add_new_user(data))
            users = _run(get_user_by_email(email))
            assert isinstance(users, (tuple, list))


class TestRedactorPermissions:
    def test_is_user_subject_redactor_returns_bool(self):
        from db import is_user_subject_redactor
        assert isinstance(_run(is_user_subject_redactor(1, 1)), bool)

    def test_is_user_topic_redactor_returns_bool(self):
        from db import is_user_topic_redactor
        assert isinstance(_run(is_user_topic_redactor(1, 1)), bool)

    def test_is_user_task_redactor_returns_bool(self):
        from db import is_user_task_redactor
        assert isinstance(_run(is_user_task_redactor(1, 1)), bool)


class TestStudentAttempts:
    def test_save_student_attempt_returns_bool(self):
        from db import save_student_attempt
        result = _run(save_student_attempt(
            user_id=1, task_id=1, is_correct=True,
            answer_text="test answer",
        ))
        assert isinstance(result, bool)

    def test_save_student_attempt_with_file(self):
        from db import save_student_attempt
        result = _run(save_student_attempt(
            user_id=1, task_id=1, is_correct=None,
            file_path="/tmp/test_file.txt",
        ))
        assert isinstance(result, bool)


class TestAttachments:
    def test_add_task_attachment(self):
        from db import add_task_attachment
        _run(add_task_attachment(
            task_id=1, file_path="/tmp/test.pdf", file_name="test.pdf",
        ))
