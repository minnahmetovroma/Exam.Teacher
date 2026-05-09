from flask import Flask
from flask_login import LoginManager
from routes.title import title_bp
from routes.profile import profile_bp
from routes.auth import auth_bp, User
from routes.subjects import subjects_bp


app = Flask(__name__)
app.config['SECRET_KEY'] = '3f8bac792189715227c86a13492ee976e4fe757c8b7aa5926b715c15e1416717'

login_manager = LoginManager(app)
@login_manager.user_loader
def load_user(user_id):
    user = User().fromDB(user_id)
    if user._user:
        return user
    return None

app.register_blueprint(title_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(subjects_bp)

if __name__ == '__main__':
    app.run()