import os

import flask
import flask_login

app_singleton = None

def create_flask_application(test_config=None):
    global app_singleton
    if app_singleton is not None:
        return app_singleton

    # create and configure the app
    app = flask.Flask(__name__, instance_relative_config=False)

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('defaultconfig.py', silent=True)
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    app_singleton = app
    return app_singleton

login_manager_singleton = None
def get_login_manager():
	global login_manager_singleton
	if login_manager_singleton is not None:
		return login_manager_singleton
	login_manager_singleton = flask_login.LoginManager()
	login_manager_singleton.init_app(create_flask_application())
	return login_manager_singleton