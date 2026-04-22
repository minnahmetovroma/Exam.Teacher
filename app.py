from flask import Flask, render_template
import db

app = Flask(__name__)

@app.route('/')
def hello_exam():
    return render_template('index.html')


@app.route('/subjects')
def subjects_list():
    all_subjects = db.get_all_subjects()
    return render_template('list.html',
                           title="Все предметы",
                           items=all_subjects,
                           url_prefix="/subjects"
                           )

@app.route('/subjects/<int:subject_id>/')
def topics_list(subject_id):
    subject = db.get_subject_by_id(subject_id)
    topics = db.get_topics_by_subject_id(subject_id)
    if subject:
        if subject[0]:
            return render_template('list.html',
                                   title=f"{subject[0][0]}",
                                   items=topics,
                                   url_prefix="/topics"
                                   )
        else:
            return render_template('list.html',
                               title=f"Такого предмета нет",
                               items=[],
                               url_prefix="/topics"
                               )

    else:
        return render_template('list.html',
                               title=f"Такого предмета нет",
                               items=[],
                               url_prefix="/topics"
                               )

# @app.route('/subjects/<str:subject_name>/')
# def topics_list(subject_id):
#

@app.route('/subjects/<int:subject_id>/<int:topic_id>')
def tasks_list(subject_id, topic_id):
    if subject_id!=db.get_subject_by_topic_id(topic_id)[0][0]:
        return render_template('list.html',
                               title=f"Такой темы",
                               items=[],
                               url_prefix="/tasks"
                               )

    topic = db.get_topic_by_id(topic_id)
    if topic:
        tasks = db.get_tasks_by_topic_id(topic_id)
        if tasks:
            all_tasks = [task[0] for task in tasks]
        else:
            all_tasks = []

        if all_tasks:
            return render_template('list.html',
                                   title=f"{topic[0][0]}",
                                   items=all_tasks,
                                   url_prefix="/tasks"
                                   )
        else:
            return render_template('list.html',
                                   title=f"{topic[0][0]}",
                                   items="Заданий нет",
                                   url_prefix="/tasks"
                                   )

    else:
        return render_template('list.html',
                               title=f"Такой темы",
                               items=[],
                               url_prefix="/tasks"
                               )



if __name__ == '__main__':
    app.run(debug=True)