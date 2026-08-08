from src.db.db import (
    get_connection,
    user_repository,
    subject_repository,
    task_repository,
    access_repository,
    attempt_repository,
)

# Пользователи
is_in_users = user_repository.is_in_users
add_new_user = user_repository.add_new_user
get_user_by_email = user_repository.get_user_by_email
get_user_by_id = user_repository.get_user_by_id
search_users = user_repository.search_users

# Предметы
get_all_subjects = subject_repository.get_all_subjects
get_subject_by_id = subject_repository.get_subject_by_id
get_subject_creator = subject_repository.get_subject_creator
add_new_subject = subject_repository.add_new_subject
update_subject = subject_repository.update_subject
delete_subject = subject_repository.delete_subject

# Темы и задания
get_topic_creator = task_repository.get_topic_creator
get_topics_by_subject_id = task_repository.get_topics_by_subject_id
get_tasks_by_topic_id = task_repository.get_tasks_by_topic_id
get_topic_by_id = task_repository.get_topic_by_id
add_new_topic = task_repository.add_new_topic
add_new_task = task_repository.add_new_task
add_task_attachment = task_repository.add_task_attachment
get_task_attachment = task_repository.get_task_attachment
update_topic = task_repository.update_topic
delete_topic = task_repository.delete_topic
update_task_fields = task_repository.update_task_fields
delete_task = task_repository.delete_task
get_task_by_id = task_repository.get_task_by_id

# Права доступа и студенты
is_user_subject_redactor = access_repository.is_user_subject_redactor
get_subject_redactors = access_repository.get_subject_redactors
add_subject_redactor = access_repository.add_subject_redactor
remove_subject_redactor = access_repository.remove_subject_redactor
get_topic_redactors = access_repository.get_topic_redactors
add_topic_redactor = access_repository.add_topic_redactor
remove_topic_redactor = access_repository.remove_topic_redactor
is_user_topic_redactor = access_repository.is_user_topic_redactor
get_task_redactors = access_repository.get_task_redactors
add_task_redactor = access_repository.add_task_redactor
remove_task_redactor = access_repository.remove_task_redactor
is_user_task_redactor = access_repository.is_user_task_redactor
get_subject_students = access_repository.get_subject_students
add_student_subject = access_repository.add_student_subject
remove_student_subject = access_repository.remove_student_subject
get_topic_students = access_repository.get_topic_students
add_student_topic = access_repository.add_student_topic
remove_student_topic = access_repository.remove_student_topic
get_task_students = access_repository.get_task_students
add_student_task = access_repository.add_student_task
remove_student_task = access_repository.remove_student_task
get_redactor_subject_ids = access_repository.get_redactor_subject_ids

# Попытки
save_student_attempt = attempt_repository.save_student_attempt
get_student_attempts = attempt_repository.get_student_attempts
get_task_submissions = attempt_repository.get_task_submissions
update_attempt_review = attempt_repository.update_attempt_review
get_submission_file_path = attempt_repository.get_submission_file_path

__all__ = [
    "get_connection",
    "is_in_users",
    "add_new_user",
    "get_user_by_email",
    "get_user_by_id",
    "search_users",
    "get_all_subjects",
    "get_subject_by_id",
    "get_subject_creator",
    "add_new_subject",
    "update_subject",
    "delete_subject",
    "get_topic_creator",
    "get_topics_by_subject_id",
    "get_tasks_by_topic_id",
    "get_topic_by_id",
    "add_new_topic",
    "add_new_task",
    "add_task_attachment",
    "get_task_attachment",
    "update_topic",
    "delete_topic",
    "update_task_fields",
    "delete_task",
    "get_task_by_id",
    "is_user_subject_redactor",
    "get_subject_redactors",
    "add_subject_redactor",
    "remove_subject_redactor",
    "get_topic_redactors",
    "add_topic_redactor",
    "remove_topic_redactor",
    "is_user_topic_redactor",
    "get_task_redactors",
    "add_task_redactor",
    "remove_task_redactor",
    "is_user_task_redactor",
    "get_subject_students",
    "add_student_subject",
    "remove_student_subject",
    "get_topic_students",
    "add_student_topic",
    "remove_student_topic",
    "get_task_students",
    "add_student_task",
    "remove_student_task",
    "get_redactor_subject_ids",
    "save_student_attempt",
    "get_student_attempts",
    "get_task_submissions",
    "update_attempt_review",
    "get_submission_file_path",
]
