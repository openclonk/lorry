from flask_sqlalchemy import SQLAlchemy
import sqlalchemy
from sqlalchemy.orm import backref
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR, TIMESTAMP
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.associationproxy import association_proxy
import pathlib
import datetime
import dicttoxml
import hashlib
import uuid
import slugify
import json

from ..utils.resources import resource_manager
from .. import core

app = core.create_flask_application()
db = SQLAlchemy(app)


class User(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	# External ID for SSO service.
	external_id = db.Column(db.Integer, index=True)
	
	name = db.Column(db.String)
	# Whether this user can edit other people's things.
	is_moderator = db.Column(db.Boolean, default=False)

	@property
	def is_authenticated(self):
		return True

	@property
	def is_active(self):
		return True

	@property
	def is_anonymous(self):
		return False

	def get_id(self):
		return str(self.id)

class EditableResource(object):
	id = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, primary_key=True)

	@declared_attr
	def owner(cls):
		return db.Column(db.Integer, db.ForeignKey(User.id))

	creation_date = db.Column(db.TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
	modification_date = db.Column(db.TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))

class Tag(db.Model):
	__tablename__ = "tag"
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String(32))

class Package(EditableResource, db.Model):
	__tablename__ = "package"
	title = db.Column(db.String)
	description = db.Column(db.String)
	author = db.Column(db.String)
	search_text = db.Column(TSVECTOR)

	tags = db.relationship(Tag, secondary="packagetagassociation")
	resources = db.relationship("Resource", cascade="all,delete-orphan")

	__table_args__ = (
		db.Index('pck_text_idx', search_text, postgresql_using='gin'),
	)

	# Immutable collection of tags that have an icon assigned.
	tags_with_icons = set((
		".scenario", ".objects", 
		"melee", "race", "settlement",
		"puzzle", "adventure", "multiplayer"))

	def has_all_tags(self, tags):
		own_tags = set((t.title for t in self.tags))
		return len((tags & own_tags)) == len(tags)

	def get_slug(self):
		return slugify.slugify(self.title, max_length=32)

	def get_tags_string(self, skip_automatic_tags=False):
		return ", ".join([t.title for t in self.tags if ((not skip_automatic_tags) or t.title[0] != ".")])

	def get_tags_with_icons(self):
		for tag in self.tags:
			tag = tag.title
			if tag in self.tags_with_icons:
				if tag[0] == ".":
					yield tag[1:], tag
				else:
					yield tag, tag
			elif tag.startswith("openclonk-"):
				yield "openclonk", tag

	def get_dependency_string(self):
		"""Returns the dependencies as a json string that can be passed to tagify.
		"""
		return json.dumps([dict(value="{} {}".format(d.dependency.id.hex, d.dependency.title)) for d in self.dependencies])

	def is_dependent_on(self, other_package):
		"""Recursively checks whether dependencies contain the other package.
		"""
		already_checked_ids = set()
		dependencies = list(self.dependencies)
		while len(dependencies) > 0:
			dependency_info = dependencies.pop()
			already_checked_ids.add(dependency_info.dependency_id)
			if dependency_info.dependency_id == other_package.id:
				return True

			# Recursively add dependencies.
			for recursive_dependency in dependency_info.dependency.dependencies:
				if recursive_dependency.dependency_id in already_checked_ids:
					continue
				dependencies.append(recursive_dependency)
			
		return False

	def update_search_text(self):
		all_text = " ".join((slugify.slugify(s, separator=" ") for s in (self.title, self.description, self.author) + tuple((t.title for t in self.tags)) if s))
		self.search_text = sqlalchemy.func.to_tsvector(all_text)

	def to_dict(self, detailed=False):
		d = {
			"id": self.id.hex,
			"title": self.title,
			"author": self.author,
			"slug": self.get_slug(),
			"description": self.description,
			"updatedAt": self.modification_date.isoformat(),
			"tags": [t.title for t in self.tags]
		}

		if detailed:
			d["dependencies"] = [d.dependency_id.hex for d in self.dependencies]
			d["files"] = []
			for f in self.resources:
				d["files"].append({
					"id": f.id.hex,
					"filename": f.original_filename,
					"length": f.size,
					"sha1": f.sha1,
					"md5": f.md5,
				})

		return d

	def to_xml(self, **kwargs):
		return dicttoxml.dicttoxml(self.to_dict(**kwargs))

class PackageTagAssociation(db.Model):
	__tablename__ = 'packagetagassociation'
	tag_id = db.Column(db.Integer, db.ForeignKey(Tag.id), primary_key=True)
	package_id = db.Column(UUID(as_uuid=True), db.ForeignKey(Package.id), primary_key=True)

class PackageDependencies(db.Model):
	__tablename__ = 'packagedependencies'
	package_id = db.Column(UUID(as_uuid=True), db.ForeignKey(Package.id), index=True, primary_key=True)
	dependency_id = db.Column(UUID(as_uuid=True), db.ForeignKey(Package.id), primary_key=True)

	def __init__(self, dependency):
		self.dependency = dependency

	package = db.relationship(Package,
								primaryjoin=(package_id == Package.id),
								backref=backref("dependencies", cascade="all,delete,delete-orphan"))
	dependency = db.relationship(Package,
								primaryjoin=(dependency_id == Package.id),
								backref=backref("dependants", cascade="all,delete,delete-orphan"))

class Resource(EditableResource, db.Model):
	__tablename__ = 'resource'
	package_id = db.Column(UUID(as_uuid=True), db.ForeignKey(Package.id))
	package = db.relationship("Package", back_populates="resources")
	original_filename = db.Column(db.String)
	size = db.Column(db.Integer)
	md5 = db.Column(db.String, nullable=False)
	sha1 = db.Column(db.String, nullable=False)
	
	def init_from_file_storage(self, filename, storage):
		self.original_filename = filename
		self.assign_hashes_from_buffer(storage)
		# After hashing, the file pointer will be at the end.
		self.size = storage.tell()
		storage.stream.seek(0)
		resource_manager.store_from_file_storage(self.sha1, storage.stream)

	def init_from_path(self, path):
		path = pathlib.Path(path)
		self.original_filename = path.name
		self.size = path.stat().st_size
		self.assign_hashes_from_file(path)
		resource_manager.store_from_filesystem(self.sha1, path)

	def assign_hashes_from_file(self, path):
		with open(path, "rb") as f:
			return self.assign_hashes_from_buffer(f)

	def assign_hashes_from_buffer(self, f):
		sha1 = hashlib.sha1()
		md5 = hashlib.md5()

		while True:
			data = f.read(2**16)
			if not data:
				break
			sha1.update(data)
			md5.update(data)

		self.sha1 = sha1.hexdigest()
		self.md5 = md5.hexdigest()
	
	def get_physical_directory_and_filename(self):
		return resource_manager.get_resource_directory_and_filename(self.sha1)

	# https://stackoverflow.com/a/43690506
	def get_pretty_printed_size(self, decimal_places=1):
		size = self.size
		for unit in ['B','KiB','MiB','GiB','TiB']:
			if size < 1024.0:
				break
			size /= 1024.0
		return f"{size:.{decimal_places}f}{unit}"




