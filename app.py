from flask import Flask, render_template, request, redirect, url_for, flash
import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, current_user, login_required, logout_user

app = Flask(__name__)
app.config['SECRET_KEY'] = '3f8bac792189715227c86a13492ee976e4fe757c8b7aa5926b715c15e1416717'
login_manager = LoginManager(app)

@app.route('/')
def title_list():
    return render_template('index.html')


@app.route('/subjects')
@login_required
def subjects_list():
    all_subjects = db.get_all_subjects()
    return render_template('list.html',
                           title="Все предметы",
                           items=all_subjects,
                           url=f"subjects"
                           )

@app.route('/subjects/<int:subject_id>')
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

@app.route('/subjects/<int:subject_id>/<int:topic_id>')
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

class User(UserMixin):

    def fromDB(self, user_id):
        self._user = db.get_user_by_id(int(user_id))
        return self

    def create(self, user):
        self._user = user
        return self

    def is_authenticated(self):
        return True
    def is_active(self):
        return True
    def is_anonymous(self):
        return False
    def get_id(self):
        return str(self._user['id'])

@login_manager.user_loader
def load_user(user_id):
    user = User().fromDB(user_id)
    if user._user:
        return user
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))

    title = request.args.get('title', '')
    color = request.args.get('color', 'red')
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        users = db.get_user_by_email(email)

        if not users:
            return render_template('login.html', title='Такого пользователя нет', color=color)
        for user in users:
            if check_password_hash(user['password_hash'], password):
                user_login = User().create(user)
                login_user(user_login, remember=True)
                return redirect(url_for('title_list'))


        return render_template('login.html', title='Неверный пароль', color=color)





    return render_template('login.html', title=title, color = color)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form.to_dict()
        if data['password'] != data['password_repeat']:
            return render_template('register.html', title='Пароли не совпадают', color='red')

        if db.is_in_users(data):
            return render_template('register.html', title='Такой пользователь уже создан', color='red')


        data['password_hash'] = generate_password_hash(data['password'])
        if data["is_teacher"] == 'yes':
            data["is_teacher"] = 1
        else:
            data["is_teacher"] = 0


        del data['password'], data['password_repeat']
        db.add_new_user(data)

        return redirect(url_for('login', title="Вы зарегистрировались, войдите", color='green'))



    return render_template('register.html', title='')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', **current_user._user)


if __name__ == '__main__':
    app.run()