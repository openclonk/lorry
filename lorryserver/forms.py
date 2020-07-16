from wtforms import BooleanField, StringField, validators, PasswordField, MultipleFileField, SelectMultipleField
from wtforms.widgets import TextArea, ListWidget, CheckboxInput
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed

from . import core
app = core.create_flask_application()

class RegistrationForm(FlaskForm):
	username = StringField('Username', [validators.Length(min=4, max=25)])
	email = StringField('Email Address', [validators.Email()])

	password = PasswordField('Password', [validators.InputRequired(), validators.EqualTo('confirm', message='Passwords must match')])
	confirm = PasswordField('Repeat Password')

class LoginForm(FlaskForm):
	email = StringField('Email Address', [validators.Email()])
	password = PasswordField('Password')

class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class UploadForm(FlaskForm):
	title = StringField("Title", [validators.Length(min=3, max=64)])
	author = StringField("Author")
	description = StringField("Short description of 50-150 characters", [validators.Length(min=50, max=150)], widget=TextArea(),
								render_kw={"minlength": 50, "maxlength": 150})
	delete_entry = StringField("Delete")
	
	tags = StringField("Tags")
	dependencies = StringField("Dependencies")

	files = MultipleFileField("Upload file(s)", [FileAllowed(app.config.get("ALLOWED_FILE_EXTENSIONS"))], render_kw={'multiple': True})
	remove_existing_files = MultiCheckboxField("Delete existing files", choices=[])

	def __init__(self, existing_package=None, **kwargs):
		super().__init__(**kwargs)

		if existing_package is not None:
			self.remove_existing_files.choices = [(file.id.hex, file.original_filename) for file in existing_package.resources]