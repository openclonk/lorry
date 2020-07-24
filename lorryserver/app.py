import base64
import flask
from flask import render_template
from wtforms.validators import ValidationError
import datetime
import flask_wtf.csrf
import flaskext.markdown
import flask_caching
import hmac
import jinja2
import dicttoxml
import slugify
import urllib
import json
import math
import uuid
import werkzeug.utils

from is_safe_url import is_safe_url
import flask_login

from . import core
from . import forms
from .utils import passwords, resources
from .db import models

app = core.create_flask_application()
flaskext.markdown.Markdown(app)
cache = flask_caching.Cache(app)
login_manager = core.get_login_manager()

# Is enabled by default.
# csrf = flask_wtf.csrf.CSRFProtect(app=app)

def dict_to_xml(dictionary):
	return dicttoxml.dicttoxml(dictionary, attr_type=False)

@login_manager.user_loader
def load_user(user_id):
	try:
		user_id = int(user_id)
	except:
		return None
	return models.User.query.get(user_id)

@cache.memoize()
def get_all_package_ids(keywords=None, limit_to_tags=None, start=0, limit=None, sort_string=None):
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
	if start > 0 and start is not None:
		packages = packages[start:]
	if limit is not None:
		packages = packages[:limit]

	return [package.id for package in packages], n_total

def get_all_packages(**kwargs):
	package_ids, n_total = get_all_package_ids(**kwargs)
	packages = models.Package.query.filter(models.Package.id.in_(package_ids)).all()
	# Query might return objects in arbitrary order.
	packages = sorted(packages, key=lambda p: package_ids.index(p.id))
	return packages, n_total

def get_package_for_raw_package_id(package_id):
	""" Note that the ID here is user input.
	"""

	try:
		parsed_id = uuid.UUID(package_id)
		package = models.Package.query.get(parsed_id)
	except:
		package = None
	
	return package

def get_logged_in_user(external_id, username, is_moderator=False):
	try:
		external_id = int(external_id)
	except:
		return None

	user = models.User.query.filter_by(external_id=external_id).first()

	if user:
		# Update the data in case the name changed etc.
		user.name = username
		user.is_moderator = is_moderator
	else:
		# Create a new user and log them in.
		user = models.User(external_id=external_id, name=username, is_moderator=is_moderator)
		models.db.session.add(user)
		models.db.session.flush()

	models.db.session.commit()
	flask_login.login_user(user, remember=True)
	return user

def check_and_remove_resources(hashes):
	for hash in hashes:
		remaining_entries = models.Resource.query.filter_by(sha1=hash).count()
		# Check if there are files with that hash remaining.
		if remaining_entries > 0:
			continue
		resources.resource_manager.remove_resource(hash)

def check_and_prepare_removal_of_orphaned_tags(tag_ids):	
	"""Note that this does not commit the session but instead has to be executed in another transaction.
	"""
	for tag_id in tag_ids:
		tagged_entries = models.PackageTagAssociation.query.filter_by(tag_id=tag_id).count()
		if tagged_entries > 0:
			continue
		models.db.session.delete(models.Tag.query.get(tag_id))
	

@app.route('/login', methods=['GET', 'POST'])
def login_page():
	if flask_login.current_user.is_authenticated:
		return flask.redirect(flask.url_for("index"))

	# Assume that SSO is configured.
	sso_endpoint = app.config.get("SSO_ENDPOINT")
	if not sso_endpoint:
		if app.config.get("DEBUG") == True:
			# Log in arbitrary users in debug mode.
			get_logged_in_user(int(flask.request.args["id"]), flask.request.args["username"], flask.request.args["is_moderator"] == "1")
			return flask.redirect(flask.url_for('index'))
		return flask.abort(404)
	
	if "sso" in flask.request.args:
		# The user has already logged in. Process the SSO service response.
		# Verify the response signature first.
		if not passwords.verify_sso_response_signature(flask.request.args["sso"].encode(), flask.request.args["sig"], app.config.get("SSO_HMAC_SECRET")):
			flask.session.clear()
			return flask.abort(403)
		# Parse response.
		sso_response = base64.decodestring(flask.request.args["sso"].encode()).decode()
		sso_response = urllib.parse.parse_qs(sso_response)
		# Same local user that did the request?
		if ("nonce" not in flask.session) or (flask.session["nonce"] != sso_response["nonce"][0]):
			flask.session.clear()
			return flask.abort(403)
		flask.session.pop("nonce", None)
		
		# Retrieve or create user.
		is_moderator = False
		groups = []
		external_id, username = sso_response["external_id"][0], sso_response["username"][0]
		if "groups" in sso_response:
			 groups = sso_response["groups"][0]
		if len(groups) > 0 and groups:
			groups = groups.split(",")
			if "Lorry Moderators" in groups:
				is_moderator = True

		user = get_logged_in_user(external_id, username, is_moderator)
		if user is None:
			print("User could not be created")
			return flask.abort(500)

		assert flask_login.current_user.is_authenticated

		forward_to = flask.session["forward_to"]
		if (forward_to is not None) and not is_safe_url(forward_to, allowed_hosts=[app.config.get("own_host")]):
			return flask.abort(400)
		flask.session.pop("forward_to", None)
		return flask.redirect(forward_to or flask.url_for('index'))

	flask.session["nonce"] = passwords.generate_nonce()
	flask.session["forward_to"] = flask.request.args.get('next')

	payload = dict(nonce=flask.session["nonce"])
	payload = urllib.parse.urlencode(payload)
	payload = base64.b64encode(payload.encode())
	payload = dict(sig=passwords.generate_sso_payload_signature(payload, app.config.get("SSO_HMAC_SECRET")),
					sso=payload.decode())
	return flask.redirect("{}?{}".format(sso_endpoint, urllib.parse.urlencode(payload)))

@app.route('/logout')
@flask_login.login_required
def logout_page():
	flask_login.logout_user()
	flask.session.clear()
	response = flask.make_response(flask.redirect(flask.url_for("index")))
	# Forcibly expire the "remember_me" token.
	response.set_cookie("remember_token", "", expires=datetime.datetime.now() - datetime.timedelta(days=1))
	return response

def get_all_packages_for_suggestion_list():
	package_data = models.Package.query.with_entities(models.Package.id, models.Package.title).all()
	package_data = [dict(value="{} {}".format(id.hex, title)) for (id, title) in package_data]
	return json.dumps(package_data)

@app.route('/upload', methods=['GET', 'POST'], defaults=dict(package_id=None))
@app.route('/upload/<string:package_id>', methods=['GET', 'POST'])
@flask_login.login_required
def upload(package_id):

	existing_package = None
	is_updating_existing_package = package_id is not None
	# Quickly verify package ID.
	if is_updating_existing_package:
		existing_package = get_package_for_raw_package_id(package_id)
		if existing_package is None:
			return flask.abort(400)
		if (existing_package.owner != flask_login.current_user.id) and not flask_login.current_user.is_moderator:
			return flask.abort(403)

	form_kwargs = dict()
	if is_updating_existing_package:
		# Pre-populate fields when updating.
		form_kwargs["title"] = existing_package.title
		form_kwargs["author"] = existing_package.author
		form_kwargs["description"] = existing_package.description
		form_kwargs["long_description"] = existing_package.long_description
		form_kwargs["tags"] = existing_package.get_tags_string(skip_automatic_tags=True)
		form_kwargs["dependencies"] = existing_package.get_dependency_string()
	else: # Creating new entry.
		# Edits to this field will only be saved for moderators.
		form_kwargs["author"] = flask_login.current_user.name

	form = forms.UploadForm(existing_package, **form_kwargs)
	# Normal users can not change the author field.
	if not flask_login.current_user.is_moderator:
		form.author.render_kw = dict(readonly=True)

	if form.validate_on_submit():
		# Files on the file system will be removed only after all sessions are committed.
		removed_file_hashes = []

		try:
			title, author, description, tags, raw_dependencies = form.title.data, form.author.data, form.description.data, form.tags.data, form.dependencies.data
			long_description = form.long_description.data

			# Parse and escape tags.
			if tags:
				tag_names = set((slugify.slugify(t["value"]) for t in json.loads(tags)))
			else:
				tag_names = set()
			
			# Parse and verify dependencies.
			dependencies = []
			dependency_ids = set()
			if raw_dependencies:
				for dependency_string in json.loads(raw_dependencies):
					dependency_string = dependency_string["value"].split(" ")[0]
					dependency = get_package_for_raw_package_id(dependency_string)
					if (not dependency) or ((is_updating_existing_package and (dependency.id == existing_package.id))):
						continue
					# Prevent circular dependencies.
					if is_updating_existing_package and dependency.is_dependent_on(existing_package):
						continue
					dependencies.append(dependency)
					dependency_ids.add(dependency.id)

			# Parse and verify uploaded filenames. Save them later.
			uploaded_files = dict()
			for file in form.files.data:
				secure_filename = werkzeug.utils.secure_filename(file.filename)
				if len(secure_filename) == 0:
					continue
				extension = secure_filename.split(".")[-1]
				if (extension not in app.config.get("ALLOWED_FILE_EXTENSIONS")):
					raise ValidationError("File extension not allowed: {}".format(extension))
				uploaded_files[secure_filename] = file
				extension_tag = ".{}".format(extension)

				# Automatically tag with extensions.
				if extension_tag not in tag_names:
					tag_names.add(extension_tag)

			# Actually storing the files comes a bit later after more validation.
			def save_files_from_form():
				resources = []
				for filename, file_data in uploaded_files.items():
					resource = models.Resource()
					resource.init_from_file_storage(filename, file_data)
					models.db.session.add(resource)
					resources.append(resource)
				models.db.session.flush()
				return resources

			# Search for or create tags.
			def get_all_tag_objects():
				tag_objects = []
				for tag_name in sorted(tag_names):
					if len(tag_name) < 2:
						continue
					if tag_name in (".ocs", ".ocf"):
						tag_name = ".scenario"
					elif tag_name == ".ocd":
						tag_name = ".objects"
					
					# The tags are already escaped and normalized here.
					tag = models.Tag.query.filter_by(title=tag_name).first()
					if tag is None:
						tag = models.Tag(title=tag_name)
						models.db.session.add(tag)
					tag_objects.append(tag)
				models.db.session.flush()
				return tag_objects

			if not is_updating_existing_package:
				if len(uploaded_files) == 0:
					raise ValidationError("Need at least one file.")
				if not flask_login.current_user.is_moderator:
					author = flask_login.current_user.name
				# Prepare new entry.
				new_entry = models.Package(title=title, author=author, description=description, long_description=long_description,
										   owner=flask_login.current_user.id, tags=get_all_tag_objects())
				new_entry.update_search_text()
				new_entry.resources = save_files_from_form()
				models.db.session.add(new_entry)
				models.db.session.flush()
				package_id = new_entry.id.hex
			else:
				# Remember old tags so we know what we might need to delete later.
				old_tag_ids = set()
				for tag in existing_package.tags:
					old_tag_ids.add(tag.id)

				# Is the package marked for deletion?
				if form.delete_entry.data:
					if (form.delete_entry.data != existing_package.title):
						raise ValidationError("Package deletion failed. Title was not confirmed.")
					for file in existing_package.resources:
						if file.id.hex not in removed_file_hashes:
							removed_file_hashes.append(file.sha1)
					# All the other things will be deleted in a cascade.
					models.db.session.delete(existing_package)
					models.db.session.flush()
					package_id = None
					check_and_prepare_removal_of_orphaned_tags(old_tag_ids)
				else:
					# Not deleted this time. Update everything.
					search_index_changed = (existing_package.title != title) or (existing_package.author != author) or (existing_package.description != description)
					existing_package.title = title
					# Only admins can set the package title manually.
					if flask_login.current_user.is_moderator:
						existing_package.author = author
					existing_package.description = description
					existing_package.long_description = long_description
					existing_package.modification_date = datetime.datetime.now(datetime.timezone.utc)

					if search_index_changed:
						existing_package.update_search_text()

					# Remove all explicitely removed or freshly uploaded files.
					files_to_remove = set((f for f in form.remove_existing_files.data))
					for new_filename in uploaded_files:
						for old_file in existing_package.resources:
							if old_file.original_filename == new_filename:
								files_to_remove.add(old_file.id.hex)

					for file in list(existing_package.resources):
						if file.id.hex in files_to_remove:
							removed_file_hashes.append(file.sha1)
							existing_package.resources.remove(file)

					existing_package.resources.extend(save_files_from_form())
					if (len(existing_package.resources) + len(uploaded_files)) == 0:
						raise ValidationError("Need at least one remaining file.")

					# Update tags with all old file extensions.
					for resource in existing_package.resources:
						extension_index = resource.original_filename.rfind(".")
						if extension_index == -1:
							continue
						extension = resource.original_filename[extension_index:]
						if len(extension) > 1:
							tag_names.add(extension.lower())

					# Update tags.
					existing_package.tags = get_all_tag_objects()
					removed_tags = old_tag_ids - set((tag.id for tag in existing_package.tags))
					check_and_prepare_removal_of_orphaned_tags(removed_tags)

					# Remove old dependencies.
					existing_dependencies = set()
					for dependency_info in list(existing_package.dependencies):
						if dependency_info.dependency_id not in dependency_ids:
							existing_package.dependencies.remove(dependency_info)
						else:
							existing_dependencies.add(dependency_info.dependency_id)
					# And add new dependencies.
					for dependency in dependencies:
						if dependency.id not in existing_dependencies:
							existing_package.dependencies.append(models.PackageDependencies(dependency))

			models.db.session.commit()

			if removed_file_hashes:
				check_and_remove_resources(removed_file_hashes)

		except ValidationError as e:
			models.db.session.rollback()
			return flask.render_template('upload.html', form=form, error=str(e), existing_package=existing_package,
											dependencies_whitelist=get_all_packages_for_suggestion_list())

		if package_id is not None:
			return flask.redirect(flask.url_for("package_details_page", package_id=package_id))
		return flask.redirect(flask.url_for("index"))

	return flask.render_template('upload.html', form=form, error="", existing_package=existing_package,
									dependencies_whitelist=get_all_packages_for_suggestion_list())

def get_packages_for_current_request():
	from flask import request

	search_query = request.args.get("q", default=None, type=str)
	sort_string = request.args.get("sort", default="-updatedAt", type=str)
	tags = request.args.get("tags", default=None, type=str)
	limit = request.args.get("limit", default=50, type=int)
	offset = request.args.get("skip", default=0, type=int)

	page_metadata = dict(search_query=search_query, sort_string=sort_string, tags=tags, limit=limit)

	if tags is not None:
		tags = tags.split(",")
	if search_query is not None:
		search_query = search_query.split(" ")
	packages, n_total = get_all_packages(keywords=search_query, limit_to_tags=tags, start=offset, limit=limit, sort_string=sort_string)

	return packages, n_total, offset, limit, page_metadata

@app.route("/")
def index():
	from flask import request

	packages, n_total, offset, limit, page_metadata = get_packages_for_current_request()
	total_pages = math.ceil(n_total / limit)
	page_index = math.ceil(offset / limit)

	package_list_cache_key = "_".join((p.id.hex for p in packages))

	return render_template("overview.html", packages=packages, total_pages=total_pages, page_index=page_index, n_total=n_total,
							previous_offset=offset - limit, next_offset=offset + limit, page_metadata=page_metadata, package_list_cache_key=package_list_cache_key)

@app.route("/uploads/<string:package_id>", methods=["GET"])
def package_details_page(package_id):

	package = get_package_for_raw_package_id(package_id)

	if package is None:
		flask.abort(404, description="File not found.")

	return render_template("package_details.html", package=package)

@app.route("/fetch_tag_suggestion", methods=["GET"])
@flask_login.login_required
def fetch_tag_suggestion():

	tag_string = slugify.slugify(flask.request.args.get("tag"))
	possible_tags = [tag_string] + [t.title for t in models.Tag.query.filter(models.Tag.title.like("%{}%".format(tag_string))).all() if t.title[0] != "."]
	return flask.jsonify([dict(value=d, searchBy=tag_string) for d in possible_tags])

@app.route("/api/uploads/<string:package_id>", methods=["GET"])
def get_package_info(package_id):

	package = get_package_for_raw_package_id(package_id)

	if package is not None:
		package_data = package.to_dict(detailed=True)
	else:
		package_data = dict()

	return flask.Response(dict_to_xml(package_data), mimetype='text/xml')


@app.route("/api/uploads", methods=["GET"])
def get_package_list():
	
	packages, n_total, offset, limit, page_metadata = get_packages_for_current_request()

	reply = {
		"meta": {
				"total": len(packages),
				"skip": offset,
		},
		"resources": [p.to_dict() for p in packages],
	}

	return flask.Response(dict_to_xml(reply), mimetype='text/xml')

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
