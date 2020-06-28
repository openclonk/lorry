import flask
from flask import render_template
from wtforms.validators import ValidationError
import flask_wtf.csrf
import jinja2
import dicttoxml
import slugify
import json
import uuid

from is_safe_url import is_safe_url
import flask_login

from . import core
from . import forms
from .utils import passwords, resources
from .db import models

app = core.create_flask_application()
login_manager = core.get_login_manager()

# Is enabled by default.
# csrf = flask_wtf.csrf.CSRFProtect(app=app)

@login_manager.user_loader
def load_user(user_id):
	try:
		user_id = int(user_id)
	except:
		return None
	return models.User.query.get(user_id)

def get_all_packages(keywords=None, limit_to_tags=None, start=0, limit=None, sort_string=None):
	packages = models.Package.query
	if limit_to_tags is not None:
		limit_to_tags = set(limit_to_tags)
		packages = packages.filter(models.Package.tags.any(models.Tag.title.in_(limit_to_tags)))
	if keywords is not None:
		search_string = " | ".join((slugify.slugify(s) for s in keywords))
		packages = packages.filter(models.Package.search_text.match(search_string))
	packages = packages.all()

	if limit_to_tags is not None:
		# The query returns a logical or on the tags. Need a logical and.
		packages = [p for p in packages if p.has_all_tags(limit_to_tags)]

	if sort_string is not None and len(sort_string) > 0:
		descending = False
		if sort_string[0] == "-":
			descending = True
			sort_string = sort_string[1:]
		sort_key = None
		if sort_string == "votes":
			sort_key = None # todo
		elif sort_string == "title":
			sort_key = lambda p: p.title
		elif sort_string == "updatedAt":
			sort_key = lambda p: p.modification_date
		
		if sort_key is not None:
			packages = sorted(packages, key=sort_key, reverse=descending)

	n_total = len(packages)
	if limit is not None:
		packages = packages[start:limit]
	return packages, n_total

def get_logged_in_user(email, password):
	user = models.User.query.filter_by(email=email).first()
	if not user:
		# Still do the password run to make timing attacks harder.
		passwords.hash_password(password)
		raise ValidationError("Incorrect login information provided.")
	if not passwords.check_hashed_password(password, user.password):
		raise ValidationError("Incorrect login information provided.")
	
	flask_login.login_user(user, remember=True)
	return user

@app.route('/login', methods=['GET', 'POST'])
def login():
	if flask_login.current_user.is_authenticated:
		return flask.redirect(flask.url_for("index"))

	form = forms.LoginForm()
	if form.validate_on_submit():
		email, password = form.email.data, form.password.data
		try:
			user = get_logged_in_user(email, password)
			assert flask_login.current_user.is_authenticated
		except ValidationError as e:
			return flask.render_template('login.html', form=form, error=str(e))

		forward_to = flask.request.args.get('next')
		if (forward_to is not None) and not is_safe_url(forward_to, allowed_hosts=[app.config.get("own_host")]):
			return flask.abort(400)

		return flask.redirect(forward_to or flask.url_for('index'))
	return flask.render_template('login.html', form=form, error="")

@app.route('/upload', methods=['GET', 'POST'])
@flask_login.login_required
def upload():
	form = forms.UploadForm()
	if form.validate_on_submit():
		try:
			title, author, description, tags = form.title.data, form.author.data, form.description.data, form.tags.data
			
			# Prepare new entry.
			new_entry = models.Package(title=title, author=author, description=description, owner=flask_login.current_user.id)
			print((title, description, tags))
			
			# Search for or create tags.
			tag_names = [t["value"] for t in json.loads(tags)]
			for tag_name in tag_names:
				# Escaping, normalizing, etc..
				tag_name = slugify.slugify(tag_name)
				tag = models.Tag.query.filter_by(title=tag_name).first()
				if tag is None:
					tag = models.Tag(title=tag_name)
					models.db.session.add(tag)
				new_entry.tags.append(tag)

			models.db.session.add(new_entry)
			models.db.session.commit()

		except ValidationError as e:
			return flask.render_template('upload.html', form=form, error=str(e))

		forward_to = flask.request.args.get('next')
		if (forward_to is not None) and not is_safe_url(forward_to, allowed_hosts=[app.config.get("own_host")]):
			return flask.abort(400)

		return flask.redirect(forward_to or flask.url_for('index'))
	return flask.render_template('upload.html', form=form, error="")

@app.route("/")
def index():
	packages, n_total = get_all_packages(limit=10)

	return render_template("overview.html", packages=packages)

@app.route("/fetch_tag_suggestion", methods=["GET"])
@flask_login.login_required
def fetch_tag_suggestion():
	from flask import request

	tag_string = request.args.get("tag")
	return flask.jsonify([dict(value=d, searchBy=tag_string) for d in "This is sparta".split(" ")])

@app.route("/api/uploads/<string:package_id>", methods=["GET"])
def get_package_info(package_id):

	package_data = dict()
	try:
		parsed_id = uuid.UUID(package_id)
		package = models.Package.query.get(parsed_id)
	except:
		package = None

	if package is not None:
		package_data = package.to_dict(detailed=True)

	return flask.Response(dicttoxml.dicttoxml(package_data), mimetype='text/xml')


@app.route("/api/uploads", methods=["GET"])
def get_package_list():
	from flask import request

	search_query = request.args.get("q", default=None, type=str)
	sort_string = request.args.get("sort", default=None, type=str)
	tags = request.args.get("tags", default=None, type=str)
	limit = request.args.get("limit", default=50, type=int)
	offset = request.args.get("skip", default=0, type=int)

	if tags is not None:
		tags = tags.split(",")
	if search_query is not None:
		search_query = search_query.split(" ")
	packages, n_total = get_all_packages(keywords=search_query, limit_to_tags=tags, start=offset, limit=limit, sort_string=sort_string)

	reply = {
		"meta": {
				"total": len(packages),
				"skip": offset,
		},
		"resources": [p.to_dict() for p in packages],
	}

	return flask.Response(dicttoxml.dicttoxml(reply), mimetype='text/xml')

@app.route("/api/files/<string:file_id>", methods=["GET"])
def download_file(file_id):

	try:
		parsed_id = uuid.UUID(file_id)
		file_info = models.Resource.query.get(parsed_id)
	except:
		file_info = None

	if file_info is not None:
		return flask.send_file(resources.resource_manager.get_resource_path(file_info.sha1),
							mimetype="application/octet-stream",
							as_attachment=True, attachment_filename=file_info.original_filename)

	flask.abort(404, description="File not found.")
