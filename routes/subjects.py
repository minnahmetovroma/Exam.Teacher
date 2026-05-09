from flask import render_template, Blueprint
import db
from flask_login import login_required

subjects_bp = Blueprint('subjects', __name__)

@subjects_bp.route('/subjects')
@login_required
def subjects_list():
    all_subjects = db.get_all_subjects()
    return render_template('list.html',
                           title="Все предметы",
                           items=all_subjects,
                           url=f"subjects"
                           )

@subjects_bp.route('/subjects/<int:subject_id>')
@login_required
def topics_list(subject_id):
    subject = db.get_subject_by_id(subject_id)
    topics = db.get_topics_by_subject_id(subject_id)
    if subject:
        if topics:
            return render_template('list.html',
                                   title=f"{subject['name']}",
                                   items=topics,
                                   url=f"subjects/{subject_id}"
                                   )
        else:
            return render_template('list.html',
                                   title=f"{subject['name']}",
                                   items=[{'name': "Тем пока нет",}],
                                   url=f"subjects/{subject_id}"
                                   )

    else:
        return render_template('list.html',
                               title=f"Такого предмета нет",
                               items={},
                               url=f"subjects/{subject_id}"
                               )

@subjects_bp.route('/subjects/<int:subject_id>/<int:topic_id>')
@login_required
def tasks_list(subject_id, topic_id):
    topic_name = db.get_topic_by_id(topic_id)['name']
    tasks = db.get_tasks_by_topic_id(topic_id)
    if topic_name:
        if tasks:
            return render_template('list.html',
                                   title=f"{topic_name}",
                                   items=tasks,
                                   url=f"subjects/{subject_id}/{topic_id}"
                                   )
        else:
            return render_template('list.html',
                                   title=f"{topic_name}",
                                   items=[{'name': "Задач пока нет",}],
                                   url=f"subjects/{subject_id}/{topic_id}"
                                   )
    else:
        return render_template('list.html',
                               title=f"Такой темы нет",
                               items=[],
                               url=f"subjects/{subject_id}"
                               )