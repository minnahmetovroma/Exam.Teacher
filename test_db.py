
def test_db_connection():
    from db import get_connection
    connect=get_connection()
    if connect is not None:
        cursor=connect.cursor()

        cursor.execute("SELECT * FROM users")
        print(cursor.fetchall())

        cursor.close()
        connect.close()
    else:
        print("connect is None")

def test_db_subjects():
    from db import get_all_subjects
    print(get_all_subjects())

def test_db_get_subjects_id():
    from db import get_subject_by_id
    print(get_subject_by_id(11))

def test_db_topics_by_subject_id():
    from db import get_topics_by_subject_id
    print(get_topics_by_subject_id(11))

def test_get_tasks_by_topic_id():
    from db import get_tasks_by_topic_id
    print(get_tasks_by_topic_id(1))

def test_get_subject_by_topic_id():
    from db import get_subject_by_topic_id
    print(get_subject_by_topic_id(1))


def test_get_topic_by_id():
    from db import get_topic_by_id
    print(get_topic_by_id(1))