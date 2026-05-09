from flask import render_template, request, redirect, url_for, flash, Blueprint
import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, login_user, current_user, login_required, logout_user

auth_bp = Blueprint('auth', __name__)

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


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('profile.profile'))

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
                return redirect(url_for('title.title_list'))


        return render_template('login.html', title='Неверный пароль', color=color)





    return render_template('login.html', title=title, color = color)


@auth_bp.route('/register', methods=['GET', 'POST'])
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

        return redirect(url_for('auth.login', title="Вы зарегистрировались, войдите", color='green'))



    return render_template('register.html', title='')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('auth.login'))