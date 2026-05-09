from flask import render_template, Blueprint

title_bp = Blueprint('title', __name__)

@title_bp.route('/')
def title_list():
    return render_template('index.html')