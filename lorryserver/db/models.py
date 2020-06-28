from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.associationproxy import association_proxy
import pathlib
import datetime
import hashlib
import uuid
import slugify

from ..utils.resources import resource_manager
from .. import core

app = core.create_flask_application()
db = SQLAlchemy(app)


class User(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String)
	email = db.Column(db.String)
	password = db.Column(db.String)

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

	creation_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
	modification_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

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
	resources = db.relationship("Resource")

	__table_args__ = (
		db.Index('pck_text_idx', search_text, postgresql_using='gin'),
	)

	def has_all_tags(self, tags):
		own_tags = set((t.title for t in self.tags))
		return len((tags & own_tags)) == len(tags)

	def get_slug(self):
		return slugify.slugify(self.title, max_length=32)

	def get_tags_string(self):
		return ", ".join([t.title for t in self.tags])

	def update_search_text(self):
		all_text = " ".join((slugify.slugify(s, separator=" ") for s in (self.title, self.description, self.author) + tuple((t.title for t in self.tags)) if s))
		self.search_text = sqlalchemy.func.to_tsvector(all_text)

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
								backref="dependencies")
	dependency = db.relationship(Package,
								primaryjoin=(dependency_id == Package.id),
								backref="dependants")

class Resource(EditableResource, db.Model):
	__tablename__ = 'resource'
	package_id = db.Column(UUID(as_uuid=True), db.ForeignKey(Package.id))
	package = db.relationship("Package", back_populates="resources")
	original_filename = db.Column(db.String)
	size = db.Column(db.Integer)
	md5 = db.Column(db.String, nullable=False)
	sha1 = db.Column(db.String, nullable=False)
	
	def init_from_path(self, path):
		path = pathlib.Path(path)
		self.original_filename = path.name
		self.size = path.stat().st_size
		self.assign_hashes_from_file(path)
		resource_manager.store_from_filesystem(self.sha1, path)

	def assign_hashes_from_file(self, path):
		sha1 = hashlib.sha1()
		md5 = hashlib.md5()

		with open(path, "rb") as f:
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


