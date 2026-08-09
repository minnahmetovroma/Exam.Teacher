import asyncio
import hashlib
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from werkzeug.security import check_password_hash


def _run(coro):
    return asyncio.run(coro)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@pytest.fixture()
def _client():
    from src.app.app import app
    with TestClient(app, follow_redirects=False) as client:
        yield client


@pytest.fixture()
def _db():
    from src import db
    return db


@pytest.fixture()
def _uploads(tmp_path, monkeypatch):
    import src.routes.subjects as subjects_mod
    monkeypatch.setattr(subjects_mod, "UPLOADS_DIR", tmp_path)
    from src.db import db as db_mod
    monkeypatch.setattr(db_mod, "UPLOADS_DIR", tmp_path)
    return tmp_path


def _login(client, user_id):
    client.cookies.set("user_id", str(user_id))


def _flatten(data):
    if isinstance(data, (list, tuple)):
        return data
    items = []
    for key, value in data.items():
        if isinstance(value, (list, tuple)):
            items.extend((key, str(v)) for v in value)
        else:
            items.append((key, str(value)))
    return items


def _post_form(client, url, data=None, files=None):
    if data is None:
        data = {}
    if files is not None:
        return client.post(url, data=data, files=files)
    body = urlencode(_flatten(data))
    return client.post(
        url,
        content=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def _redirect_url(resp):
    assert resp.next_request is not None, resp.status_code
    return resp.next_request.url


def _subject_id(_db, name):
    subjects = _run(_db.get_all_subjects(user_id=1, is_teacher=True))
    for subject in subjects:
        if subject.name == name:
            return subject.id
    return None


def _topic_id(_db, subject_id, name):
    topics = _run(_db.get_topics_by_subject_id(subject_id, user_id=1, is_teacher=True))
    for topic in topics:
        if topic.name == name:
            return topic.id
    return None


def _task_id(_db, topic_id, name):
    tasks = _run(_db.get_tasks_by_topic_id(topic_id, user_id=1, is_teacher=True))
    for task in tasks:
        if task.name == name:
            return task.id
    return None


def _create_task(_db, name, question_type='text', **kwargs):
    if question_type == 'text':
        kwargs.setdefault('correct_text', 'expected answer')
    result = _run(_db.add_new_task(
        topic_id=1,
        name=name,
        description='',
        user_id=1,
        is_public_input=True,
        question_type=question_type,
        **kwargs,
    ))
    assert result, f"failed to create task {name}"
    return int(result['id'])


class TestPublic:
    def test_root_page(self, _client):
        resp = _client.get('/')
        assert resp.status_code == 200

    def test_login_page(self, _client):
        resp = _client.get('/login/')
        assert resp.status_code == 200

    def test_register_page(self, _client):
        resp = _client.get('/register/')
        assert resp.status_code == 200


class TestRegistrationSchema:
    def _payload(self, email, password, repeat_password):
        return {
            'email': email,
            'surname': 'Api',
            'first_name': 'Schema',
            'patronymic': 'S',
            'password_hash': _sha256(f'{email}:{password}'),
            'repeat_password_hash': _sha256(f'{email}:{repeat_password}'),
            'is_teacher': 'no',
        }

    def test_passwords_match(self):
        from src.schemas import UserRegistrationSchema
        schema = UserRegistrationSchema.model_validate(
            self._payload('schema.match@example.com', 'secret', 'secret')
        )
        assert schema.password_hash == schema.repeat_password_hash

    def test_passwords_mismatch_raises(self):
        import pydantic
        from src.schemas import UserRegistrationSchema
        with pytest.raises(pydantic.ValidationError):
            UserRegistrationSchema.model_validate(
                self._payload('schema.mismatch@example.com', 'secret', 'other')
            )


class TestAuth:
    def test_login_success_sets_cookie(self, _client):
        resp = _post_form(_client, '/login/', {
            'email': 'test@example.com',
            'password': _sha256('test@example.com:password'),
        })
        assert resp.status_code == 303
        assert _redirect_url(resp).path == '/'
        assert _client.cookies.get('user_id') == '1'

    @pytest.mark.parametrize('email, password, redirect', [
        ('test@example.com', _sha256('test@example.com:wrong'), '/login/'),
        ('nobody@example.com', _sha256('nobody@example.com:wrong'), '/login/'),
    ])
    def test_login_fail(self, _client, email, password, redirect):
        resp = _post_form(_client, '/login/', {
            'email': email,
            'password': password,
        })
        assert resp.status_code == 303
        assert _redirect_url(resp).path == redirect
        assert _client.cookies.get('user_id') is None

    def test_register_password_mismatch(self, _client):
        resp = _post_form(_client, '/register/', {
            'surname': 'Api', 'name': 'Mismatch', 'patronymic': 'P',
            'email': 'api.mismatch@example.com',
            'password': _sha256('api.mismatch@example.com:a'),
            'password_repeat': _sha256('api.mismatch@example.com:b'),
            'is_teacher': 'no',
        })
        assert resp.status_code == 303
        assert _redirect_url(resp).path == '/register/'

    def test_register_duplicate_user(self, _client):
        resp = _post_form(_client, '/register/', {
            'surname': 'Seed', 'name': 'Seed', 'patronymic': 'Seed',
            'email': 'test@example.com',
            'password': _sha256('test@example.com:password'),
            'password_repeat': _sha256('test@example.com:password'),
            'is_teacher': 'no',
        })
        assert resp.status_code == 303
        assert _redirect_url(resp).path == '/register/'

    def test_register_success(self, _client, _db):
        resp = _post_form(_client, '/register/', {
            'surname': 'Api', 'name': 'Registered', 'patronymic': 'P',
            'email': 'api.register@example.com',
            'password': _sha256('api.register@example.com:password'),
            'password_repeat': _sha256('api.register@example.com:password'),
            'is_teacher': 'no',
        })
        assert resp.status_code == 303
        assert _redirect_url(resp).path == '/login/'
        users = _run(_db.get_user_by_email('api.register@example.com'))
        assert len(users) == 1
        assert not users[0].is_teacher

    def test_register_roundtrip(self, _client, _db):
        resp = _post_form(_client, '/register/', {
            'surname': 'Round', 'name': 'Trip', 'patronymic': 'User',
            'email': 'roundtrip@example.com',
            'password': _sha256('roundtrip@example.com:secret'),
            'password_repeat': _sha256('roundtrip@example.com:secret'),
            'is_teacher': 'yes',
        })
        assert resp.status_code == 303
        users = _run(_db.get_user_by_email('roundtrip@example.com'))
        assert len(users) == 1
        user = users[0]
        assert user.surname == 'Round'
        assert user.first_name == 'Trip'
        assert user.patronymic == 'User'
        assert user.email == 'roundtrip@example.com'
        assert user.is_teacher == 1
        assert check_password_hash(user.password_hash, _sha256('roundtrip@example.com:secret'))

    def test_logout_clears_cookie(self, _client):
        _login(_client, 1)
        resp = _client.get('/logout/')
        assert resp.status_code == 303
        assert _redirect_url(resp).path == '/login/'
        assert 'user_id=' in resp.headers['set-cookie']
        assert 'Max-Age=0' in resp.headers['set-cookie']


class TestAccess:
    def test_profile_requires_auth(self, _client):
        resp = _client.get('/profile/')
        assert resp.status_code == 303
        assert _redirect_url(resp).path == '/login/'

    def test_profile_with_auth(self, _client):
        _login(_client, 1)
        resp = _client.get('/profile/')
        assert resp.status_code == 200

    def test_subjects_requires_auth(self, _client):
        resp = _client.get('/subjects/')
        assert resp.status_code == 303
        assert _redirect_url(resp).path == '/login/'

    def test_subjects_page_teacher(self, _client):
        _login(_client, 1)
        resp = _client.get('/subjects/')
        assert resp.status_code == 200
        assert 'Seed subject' in resp.text

    def test_subjects_page_student(self, _client):
        _login(_client, 2)
        resp = _client.get('/subjects/')
        assert resp.status_code == 200
        assert 'Seed subject' in resp.text


class TestSubjects:
    def test_create_subject_teacher(self, _client, _db):
        _login(_client, 1)
        resp = _post_form(_client, '/subjects/', {
            'name': '__api_subject',
            'description': 'created via api',
            'is_private': 'false',
        })
        assert resp.status_code == 303
        assert _redirect_url(resp).path == '/subjects/'
        subject_id = _subject_id(_db, '__api_subject')
        assert subject_id is not None
        _run(_db.delete_subject(subject_id))

    @pytest.mark.parametrize('is_private, expected_is_public', [
        ('false', 1),
        ('true', 0),
    ])
    def test_create_subject_roundtrip(self, _client, _db, is_private, expected_is_public):
        _login(_client, 1)
        name = f'__api_subject_roundtrip_{expected_is_public}'
        resp = _post_form(_client, '/subjects/', {
            'name': name,
            'description': 'roundtrip desc',
            'is_private': is_private,
        })
        assert resp.status_code == 303
        subject_id = _subject_id(_db, name)
        assert subject_id is not None
        subject = _run(_db.get_subject_by_id(subject_id))
        assert subject.name == name
        assert subject.description == 'roundtrip desc'
        assert subject.is_public == expected_is_public
        _run(_db.delete_subject(subject_id))

    def test_create_subject_student_forbidden(self, _client):
        _login(_client, 2)
        resp = _post_form(_client, '/subjects/', {
            'name': '__api_forbidden',
            'description': '',
        })
        assert resp.status_code == 403

    def test_edit_subject_teacher(self, _client, _db):
        _login(_client, 1)
        resp = _post_form(_client, '/subjects/11/edit/', {
            'name': '__api_edited',
            'description': 'new description',
            'is_private': 'false',
        })
        assert resp.status_code == 200
        payload = resp.json()
        assert payload['status'] == 'success'
        assert payload['new_name'] == '__api_edited'
        subject = _run(_db.get_subject_by_id(11))
        assert subject.name == '__api_edited'
        _post_form(_client, '/subjects/11/edit/', {
            'name': 'Seed subject',
            'description': '',
            'is_private': 'false',
        })

    def test_edit_subject_student_forbidden(self, _client):
        _login(_client, 2)
        resp = _post_form(_client, '/subjects/11/edit/', {
            'name': 'x', 'description': '', 'is_private': 'false',
        })
        assert resp.status_code == 403

    def test_delete_subject(self, _client, _db):
        _login(_client, 1)
        _post_form(_client, '/subjects/', {
            'name': '__api_delete_me', 'description': '', 'is_private': 'false',
        })
        subject_id = _subject_id(_db, '__api_delete_me')
        assert subject_id is not None
        resp = _post_form(_client, f'/subjects/{subject_id}/delete/')
        assert resp.status_code == 200
        assert resp.json()['status'] == 'success'
        assert _run(_db.get_subject_by_id(subject_id)) is None

    def test_delete_subject_student_forbidden(self, _client):
        _login(_client, 2)
        resp = _post_form(_client, '/subjects/11/delete/')
        assert resp.status_code == 403

    def test_subject_detail_page(self, _client):
        _login(_client, 1)
        resp = _client.get('/subjects/11/')
        assert resp.status_code == 200
        assert 'Seed topic' in resp.text


class TestTopics:
    def test_create_topic_teacher(self, _client, _db):
        _login(_client, 1)
        resp = _post_form(_client, '/subjects/11/', {
            'name': '__api_topic',
            'description': 'topic via api',
        })
        assert resp.status_code == 303
        assert _redirect_url(resp).path == '/subjects/11/'
        topic_id = _topic_id(_db, 11, '__api_topic')
        assert topic_id is not None
        _run(_db.delete_topic(topic_id))

    @pytest.mark.parametrize('is_private, expected_is_public', [
        ('false', 1),
        ('true', 0),
    ])
    def test_create_topic_roundtrip(self, _client, _db, is_private, expected_is_public):
        _login(_client, 1)
        name = f'__api_topic_roundtrip_{expected_is_public}'
        resp = _post_form(_client, '/subjects/11/', {
            'name': name,
            'description': 'topic roundtrip desc',
            'is_private': is_private,
        })
        assert resp.status_code == 303
        topic_id = _topic_id(_db, 11, name)
        assert topic_id is not None
        topic = _run(_db.get_topic_by_id(topic_id))
        assert topic.name == name
        assert topic.description == 'topic roundtrip desc'
        assert topic.is_public == expected_is_public
        _run(_db.delete_topic(topic_id))

    def test_create_topic_student_forbidden(self, _client):
        _login(_client, 2)
        resp = _post_form(_client, '/subjects/11/', {
            'name': '__api_topic_forbidden',
            'description': '',
        })
        assert resp.status_code == 403

    def test_edit_topic_teacher(self, _client, _db):
        _login(_client, 1)
        _post_form(_client, '/subjects/11/', {
            'name': '__api_topic_edit', 'description': '',
        })
        topic_id = _topic_id(_db, 11, '__api_topic_edit')
        assert topic_id is not None
        resp = _post_form(_client, f'/subjects/11/{topic_id}/edit/', {
            'name': '__api_topic_edited',
            'description': 'edited',
            'is_private': 'false',
        })
        assert resp.status_code == 200
        assert resp.json()['status'] == 'success'
        topic = _run(_db.get_topic_by_id(topic_id))
        assert topic.name == '__api_topic_edited'
        _run(_db.delete_topic(topic_id))

    def test_edit_topic_student_forbidden(self, _client):
        _login(_client, 2)
        resp = _post_form(_client, '/subjects/11/1/edit/', {
            'name': 'x', 'description': '', 'is_private': 'false',
        })
        assert resp.status_code == 403

    def test_topic_detail_page(self, _client):
        _login(_client, 1)
        resp = _client.get('/subjects/11/1/')
        assert resp.status_code == 200
        assert 'Seed topic' in resp.text


class TestTasks:
    def test_create_task_text(self, _client, _db):
        _login(_client, 1)
        resp = _post_form(_client, '/subjects/11/1/', {
            'name': '__api_text_task',
            'description': '',
            'question_type': 'text',
            'correct_text': 'expected answer',
            'is_case_sensitive': '0',
        })
        assert resp.status_code == 303
        assert _redirect_url(resp).path == '/subjects/11/1/'
        task_id = _task_id(_db, 1, '__api_text_task')
        assert task_id is not None
        _run(_db.delete_task(task_id))

    @pytest.mark.parametrize('is_private, expected_is_public, is_case_sensitive', [
        ('false', 1, 0),
        ('true', 0, 1),
    ])
    def test_create_task_text_roundtrip(self, _client, _db, is_private, expected_is_public, is_case_sensitive):
        _login(_client, 1)
        name = f'__api_task_roundtrip_{expected_is_public}'
        resp = _post_form(_client, '/subjects/11/1/', {
            'name': name,
            'description': 'task roundtrip desc',
            'question_type': 'text',
            'correct_text': 'expected answer',
            'is_case_sensitive': str(is_case_sensitive),
            'is_private': is_private,
        })
        assert resp.status_code == 303
        task_id = _task_id(_db, 1, name)
        assert task_id is not None
        task = _run(_db.get_task_by_id(task_id))
        assert task.name == name
        assert task.description == 'task roundtrip desc'
        assert task.question_type == 'text'
        assert task.is_public == expected_is_public
        assert task.correct_answer == 'expected answer'
        assert task.is_case_sensitive == is_case_sensitive
        _run(_db.delete_task(task_id))

    @pytest.mark.parametrize('payload', [
        {'question_type': 'choice', 'options': ['A', 'B', 'C'], 'correct_options': ['0']},
        {'question_type': 'material'},
        {'question_type': 'file'},
    ])
    def test_create_task_variants(self, _client, _db, payload):
        _login(_client, 1)
        name = f'__api_task_{payload["question_type"]}'
        resp = _post_form(_client, '/subjects/11/1/', {
            'name': name,
            'description': '',
            **payload,
        })
        assert resp.status_code == 303
        task_id = _task_id(_db, 1, name)
        assert task_id is not None
        _run(_db.delete_task(task_id))

    @pytest.mark.parametrize('payload', [
        {'question_type': 'choice', 'options': ['A']},
        {'question_type': 'text', 'correct_text': ''},
    ])
    def test_create_task_missing_required_400(self, _client, payload):
        _login(_client, 1)
        resp = _post_form(_client, '/subjects/11/1/', {
            'name': f'__api_bad_{payload["question_type"]}',
            'description': '',
            **payload,
        })
        assert resp.status_code == 400

    def test_create_task_student_forbidden(self, _client):
        _login(_client, 2)
        resp = _post_form(_client, '/subjects/11/1/', {
            'name': '__api_task_forbidden',
            'description': '',
            'question_type': 'text',
            'correct_text': 'x',
        })
        assert resp.status_code == 403

    def test_edit_task(self, _client, _db):
        _login(_client, 1)
        task_id = _create_task(_db, '__api_task_edit')
        resp = _post_form(_client, f'/subjects/11/1/{task_id}/edit/', {
            'name': '__api_task_edited',
            'description': 'after',
            'is_private': 'false',
            'question_type': 'text',
            'correct_text': 'answer',
        })
        assert resp.status_code == 200
        assert resp.json()['status'] == 'success'
        task = _run(_db.get_task_by_id(task_id))
        assert task.name == '__api_task_edited'
        _run(_db.delete_task(task_id))

    def test_delete_task(self, _client, _db):
        _login(_client, 1)
        task_id = _create_task(_db, '__api_task_delete')
        resp = _post_form(_client, f'/subjects/11/1/{task_id}/delete/')
        assert resp.status_code == 200
        assert resp.json()['status'] == 'success'
        assert _run(_db.get_task_by_id(task_id)) is None

    def test_tasks_page_student(self, _client, _db):
        task_id = _create_task(_db, '__api_student_visible')
        _login(_client, 2)
        resp = _client.get('/subjects/11/1/')
        assert resp.status_code == 200
        assert '__api_student_visible' in resp.text
        _run(_db.delete_task(task_id))


class TestCheckAnswer:
    @pytest.mark.parametrize('correct_text, is_case_sensitive, user_answer, expected', [
        ('Answer', 0, 'answer', True),
        ('Answer', 0, 'nope', False),
        ('Answer', 1, 'answer', False),
        ('Answer', 1, 'Answer', True),
    ])
    def test_check_text(self, _client, _db, correct_text, is_case_sensitive, user_answer, expected):
        task_id = _create_task(
            _db, f'__api_check_text_{is_case_sensitive}_{user_answer}',
            correct_text=correct_text, is_case_sensitive=is_case_sensitive,
        )
        _login(_client, 2)
        resp = _post_form(_client, f'/subjects/11/1/{task_id}/check/', {
            'user_answer': user_answer,
        })
        assert resp.status_code == 200
        payload = resp.json()
        assert payload['is_correct'] is expected
        if expected:
            assert 'Правильно' in payload['message']
        _run(_db.delete_task(task_id))

    @pytest.mark.parametrize('options, correct_options, user_answer, expected', [
        (['A', 'B'], ['0'], ['0'], True),
        (['A', 'B'], ['0'], ['1'], False),
        (['A', 'B', 'C'], ['0', '1'], ['0', '1'], True),
    ])
    def test_check_choice(self, _client, _db, options, correct_options, user_answer, expected):
        task_id = _create_task(
            _db, f'__api_check_choice_{"-".join(user_answer)}_{expected}',
            question_type='choice',
            options=options, correct_options=correct_options,
        )
        _login(_client, 2)
        resp = _post_form(_client, f'/subjects/11/1/{task_id}/check/', {
            'user_answer': user_answer,
        })
        assert resp.status_code == 200
        assert resp.json()['is_correct'] is expected
        _run(_db.delete_task(task_id))

    def test_check_material_400(self, _client, _db):
        task_id = _create_task(_db, '__api_material', question_type='material')
        _login(_client, 2)
        resp = _post_form(_client, f'/subjects/11/1/{task_id}/check/')
        assert resp.status_code == 400
        assert resp.json()['is_correct'] is False
        assert 'Конспект' in resp.json()['message']
        _run(_db.delete_task(task_id))

    def test_check_nonexistent_task_404(self, _client):
        _login(_client, 2)
        resp = _post_form(_client, '/subjects/11/1/999999/check/', {
            'user_answer': 'x',
        })
        assert resp.status_code == 404

    def test_check_file_upload(self, _client, _db, _uploads):
        task_id = _create_task(_db, '__api_file_task', question_type='file')
        _login(_client, 2)
        resp = _post_form(
            _client,
            f'/subjects/11/1/{task_id}/check/',
            files={'user_answer': ('answer.txt', b'file content', 'text/plain')},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload['is_correct'] is None
        assert 'Файл успешно загружен' in payload['message']
        submissions = _run(_db.get_task_submissions(task_id))
        assert any(s.user_id == 2 for s in submissions)
        _run(_db.delete_task(task_id))

    def test_check_file_missing_400(self, _client, _db):
        task_id = _create_task(_db, '__api_file_missing', question_type='file')
        _login(_client, 2)
        resp = _post_form(_client, f'/subjects/11/1/{task_id}/check/')
        assert resp.status_code == 400
        assert 'не был прикреплен' in resp.json()['message']
        _run(_db.delete_task(task_id))


class TestManageAndAccess:
    def test_search_users(self, _client):
        _login(_client, 1)
        resp = _client.get('/users/search', params={'q': 'Seed'})
        assert resp.status_code == 200
        emails = [u['email'] for u in resp.json()]
        assert 'test@example.com' in emails

    def test_search_users_empty_query(self, _client):
        _login(_client, 1)
        resp = _client.get('/users/search', params={'q': '   '})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_users_requires_auth(self, _client):
        resp = _client.get('/users/search', params={'q': 'Seed'})
        assert resp.status_code == 303

    def test_subject_redactors_teacher(self, _client):
        _login(_client, 1)
        resp = _client.get('/subjects/11/redactors')
        assert resp.status_code == 200
        redactors = resp.json()
        assert any(r['id'] == 1 and r['protected'] for r in redactors)

    def test_subject_redactors_student_forbidden(self, _client):
        _login(_client, 2)
        resp = _client.get('/subjects/11/redactors')
        assert resp.status_code == 403

    def test_subject_students_teacher(self, _client):
        _login(_client, 1)
        resp = _client.get('/subjects/11/students')
        assert resp.status_code == 200
        assert any(s['id'] == 2 for s in resp.json())

    def test_subject_students_student_forbidden(self, _client):
        _login(_client, 2)
        resp = _client.get('/subjects/11/students')
        assert resp.status_code == 403

    @pytest.mark.parametrize('manage_url, get_redactors', [
        ('/subjects/11/manage', lambda db: _run(db.get_subject_redactors(11))),
        ('/subjects/11/1/manage', lambda db: _run(db.get_topic_redactors(1))),
    ])
    def test_manage_add_remove_redactor(self, _client, _db, manage_url, get_redactors):
        _login(_client, 1)
        resp = _post_form(_client, manage_url, {
            'action': 'add_redactor', 'target_user_id': '3',
        })
        assert resp.status_code == 200
        assert resp.json() == {'status': 'ok'}
        redactors = get_redactors(_db)
        assert any(r.id == 3 for r in redactors)
        resp = _post_form(_client, manage_url, {
            'action': 'remove_redactor', 'target_user_id': '3',
        })
        assert resp.status_code == 200
        redactors = get_redactors(_db)
        assert not any(r.id == 3 for r in redactors)

    def test_manage_subject_add_non_teacher_400(self, _client):
        _login(_client, 1)
        resp = _post_form(_client, '/subjects/11/manage', {
            'action': 'add_redactor', 'target_user_id': '2',
        })
        assert resp.status_code == 400

    def test_manage_subject_remove_creator_400(self, _client):
        _login(_client, 1)
        resp = _post_form(_client, '/subjects/11/manage', {
            'action': 'remove_redactor', 'target_user_id': '1',
        })
        assert resp.status_code == 400

    def test_manage_subject_add_remove_student(self, _client, _db):
        _login(_client, 1)
        _post_form(_client, '/subjects/', {
            'name': '__api_manage_subject', 'description': '', 'is_private': 'false',
        })
        subject_id = _subject_id(_db, '__api_manage_subject')
        assert subject_id is not None
        resp = _post_form(_client, f'/subjects/{subject_id}/manage', {
            'action': 'add_student', 'target_user_id': '2',
            'access_all_topics': 'true', 'access_all_tasks': 'true',
        })
        assert resp.status_code == 200
        students = _run(_db.get_subject_students(subject_id))
        assert any(s.id == 2 for s in students)
        resp = _post_form(_client, f'/subjects/{subject_id}/manage', {
            'action': 'remove_student', 'target_user_id': '2',
        })
        assert resp.status_code == 200
        students = _run(_db.get_subject_students(subject_id))
        assert not any(s.id == 2 for s in students)
        _run(_db.delete_subject(subject_id))

    def test_manage_topic_add_remove_redactor(self, _client, _db):
        _login(_client, 1)
        resp = _post_form(_client, '/subjects/11/1/manage', {
            'action': 'add_redactor', 'target_user_id': '3',
        })
        assert resp.status_code == 200
        redactors = _run(_db.get_topic_redactors(1))
        assert any(r.id == 3 for r in redactors)
        resp = _post_form(_client, '/subjects/11/1/manage', {
            'action': 'remove_redactor', 'target_user_id': '3',
        })
        assert resp.status_code == 200
        redactors = _run(_db.get_topic_redactors(1))
        assert not any(r.id == 3 for r in redactors)

    def test_manage_topic_student_forbidden(self, _client):
        _login(_client, 2)
        resp = _post_form(_client, '/subjects/11/1/manage', {
            'action': 'add_student', 'target_user_id': '2',
        })
        assert resp.status_code == 403

    def test_manage_task_add_remove_redactor(self, _client, _db):
        _login(_client, 1)
        task_id = _create_task(_db, '__api_manage_task')
        resp = _post_form(_client, f'/subjects/11/1/{task_id}/manage', {
            'action': 'add_redactor', 'target_user_id': '3',
        })
        assert resp.status_code == 200
        redactors = _run(_db.get_task_redactors(task_id))
        assert any(r.id == 3 for r in redactors)
        resp = _post_form(_client, f'/subjects/11/1/{task_id}/manage', {
            'action': 'remove_redactor', 'target_user_id': '3',
        })
        assert resp.status_code == 200
        redactors = _run(_db.get_task_redactors(task_id))
        assert not any(r.id == 3 for r in redactors)
        _run(_db.delete_task(task_id))

    def test_manage_task_student_forbidden(self, _client, _db):
        task_id = _create_task(_db, '__api_manage_task_fb')
        _login(_client, 2)
        resp = _post_form(_client, f'/subjects/11/1/{task_id}/manage', {
            'action': 'add_student', 'target_user_id': '2',
        })
        assert resp.status_code == 403
        _run(_db.delete_task(task_id))

    def test_submissions_list_and_review(self, _client, _db, _uploads):
        task_id = _create_task(_db, '__api_submissions', question_type='file')
        _login(_client, 2)
        _post_form(
            _client,
            f'/subjects/11/1/{task_id}/check/',
            files={'user_answer': ('sub.txt', b'submission', 'text/plain')},
        )
        _login(_client, 1)
        resp = _client.get(f'/subjects/11/1/{task_id}/submissions')
        assert resp.status_code == 200
        submissions = resp.json()
        assert any(s['user_id'] == 2 for s in submissions)
        resp = _post_form(_client, f'/subjects/11/1/{task_id}/submissions/review', {
            'user_id': '2', 'is_correct': '1',
        })
        assert resp.status_code == 200
        assert resp.json() == {'status': 'ok'}
        _run(_db.delete_task(task_id))

    def test_submissions_forbidden_student(self, _client, _db):
        task_id = _create_task(_db, '__api_submissions_fb', question_type='file')
        _login(_client, 2)
        resp = _client.get(f'/subjects/11/1/{task_id}/submissions')
        assert resp.status_code == 403
        _run(_db.delete_task(task_id))

    def test_submission_file_endpoint(self, _client, _db, _uploads):
        task_id = _create_task(_db, '__api_sub_file', question_type='file')
        _login(_client, 2)
        _post_form(
            _client,
            f'/subjects/11/1/{task_id}/check/',
            files={'user_answer': ('sub.txt', b'submission content', 'text/plain')},
        )
        _login(_client, 1)
        resp = _client.get(f'/subjects/11/1/{task_id}/submissions/2/file')
        assert resp.status_code == 200
        assert resp.content == b'submission content'
        _run(_db.delete_task(task_id))

    def test_submission_file_forbidden_student(self, _client, _db):
        task_id = _create_task(_db, '__api_sub_file_fb', question_type='file')
        _login(_client, 2)
        resp = _client.get(f'/subjects/11/1/{task_id}/submissions/2/file')
        assert resp.status_code == 403
        _run(_db.delete_task(task_id))

    def test_attachment_file_endpoint(self, _client, _db, _uploads):
        _login(_client, 1)
        resp = _post_form(
            _client,
            '/subjects/11/1/',
            {
                'name': '__api_attachment_task',
                'description': '',
                'question_type': 'material',
                'correct_text': '',
            },
            files={'task_attachments': ('note.txt', b'attachment bytes', 'text/plain')},
        )
        assert resp.status_code == 303
        tasks = _run(_db.get_tasks_by_topic_id(1, user_id=1, is_teacher=True))
        task = next((t for t in tasks if t.name == '__api_attachment_task'), None)
        assert task is not None
        assert task.attachments, 'attachment should be saved'
        attachment_id = task.attachments[0].id
        resp = _client.get(
            f'/subjects/11/1/{task.id}/attachments/{attachment_id}/file'
        )
        assert resp.status_code == 200
        assert resp.content == b'attachment bytes'
        _run(_db.delete_task(task.id))
