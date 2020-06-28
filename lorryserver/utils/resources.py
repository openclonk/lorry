import hashlib
import os
import io
import pathlib
import shutil

from .. import core

class ResourceManager():
	def __init__(self, config):
		if config is not None:
			self.set_config(config)

	def set_config(self, config):
		self.base_path = config.get("RESOURCES_PATH")
	
	def get_parent_path(self, resource_name):
		assert len(resource_name) > 4
		return pathlib.Path(self.base_path, resource_name[:2], resource_name[2:4])

	def get_resource_path(self, resource_name):
		return pathlib.Path(self.get_parent_path(resource_name), resource_name)
	
	def get_resource_directory_and_filename(self, uuid):
		return (self.base_path, uuid)

	def ensure_resource_path_valid(self, uuid):
		path = self.get_resource_path(uuid)
		# The very file already exists?
		if os.path.exists(path):
			raise ValueError("Resource identifier already present.")
		# Ensure parent path exists.
		parent = self.get_parent_path(uuid)
		parent.mkdir(parents=True, exist_ok=True)
		return path

	def store_from_memory(self, uuid, resource):
		path = self.ensure_resource_path_valid(uuid)
		with open(path, "wb") as f:
			f.write(resource)

	def store_from_filesystem(self, uuid, source_path):
		path = self.ensure_resource_path_valid(uuid)

		shutil.move(source_path, path)

	def get_resource(self, uuid):
		path = self.get_resource_path(uuid)
		with open(path, "rb") as f:
			data = io.BytesIO(f.read())
		return data

resource_manager = ResourceManager(core.create_flask_application().config)
