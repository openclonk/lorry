from wtforms import BooleanField, StringField, validators, PasswordField, MultipleFileField
from wtforms.widgets import TextArea
from flask_wtf import FlaskForm

class RegistrationForm(FlaskForm):
	username = StringField('Username', [validators.Length(min=4, max=25)])
	email = StringField('Email Address', [validators.Email()])

	password = PasswordField('Password', [validators.InputRequired(), validators.EqualTo('confirm', message='Passwords must match')])
	confirm = PasswordField('Repeat Password')

class LoginForm(FlaskForm):
	email = StringField('Email Address', [validators.Email()])
	password = PasswordField('Password')

class UploadForm(FlaskForm):
	title = StringField("Title", [validators.Length(min=3, max=32)])
	author = StringField("Author")
	description = StringField("Short description (50-150 characters)", [validators.Length(min=50, max=150)], widget=TextArea())
	tags = StringField("Tags")

	files = MultipleFileField("File(s)")