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
                           url=f"subjects"
                           )

@app.route('/subjects/<int:subject_id>/')
def topics_list(subject_id):
    subject = db.get_subject_by_id(subject_id)
    topics = db.get_topics_by_subject_id(subject_id)
    if subject:
        if topics:
            return render_template('list.html',
                                   title=f"{subject[0][0]}",
                                   items=topics,
                                   url=f"subjects/{subject_id}"
                                   )
        else:
            return render_template('list.html',
                                   title=f"{subject[0][0]}",
                                   items=[(subject_id,"Тем пока нет")],
                                   url=f"subjects/{subject_id}"
                                   )

    else:
        return render_template('list.html',
                               title=f"Такого предмета нет",
                               items=[],
                               url=f"subjects/{subject_id}"
                               )

@app.route('/subjects/<int:subject_id>/<int:topic_id>')
def tasks_list(subject_id, topic_id):
    topic = db.get_topic_by_id(topic_id)
    tasks = db.get_tasks_by_topic_id(topic_id)
    if topic:
        if tasks:
            return render_template('list.html',
                                   title=f"{topic[0][0]}",
                                   items=tasks,
                                   url=f"subjects/{subject_id}/{topic_id}"
                                   )
        else:
            return render_template('list.html',
                                   title=f"{topic[0][0]}",
                                   items=[(topic_id, "Задач пока нет")],
                                   url=f"subjects/{subject_id}"
                                   )
    else:
        return render_template('list.html',
                               title=f"Такой темы нет",
                               items=[],
                               url=f"subjects/{subject_id}"
                               )



if __name__ == '__main__':
    app.run(debug=True)