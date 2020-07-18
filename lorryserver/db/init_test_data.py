import datetime
import shutil
import tempfile
import os
from lorem_text import lorem

def init_test_data():
	from . import models
	session = models.db.session
	print("Filling database with test data...", flush=True)

	user1 = models.User(name="Larrytest", external_id=65)
	user2 = models.User(name="Larry", external_id=872)

	session.add(user1)
	session.add(user2)
	session.commit()

	tags = dict()
	for tag in ("openclonk-9", ".scenario", ".objects", "multiplayer", "advertisement", "bundle", "test",
				"race", "puzzle", "adventure", "melee"):
		t = models.Tag(title=tag)
		tags[tag] = t
		session.add(t)
	session.commit()

	yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
	last_week = datetime.datetime.now() - datetime.timedelta(days=7)

	packages = []
	packages.append(models.Package(title="Caedes", author="Zapper, KKenny", description="The very first and the very last. At least 50 chars.", owner=user1.id,
									long_description=lorem.paragraphs(5)))
	for tag in ("openclonk-9", ".objects", ".scenario", "multiplayer", "test"):
		packages[-1].tags.append(tags[tag])
	packages.append(models.Package(title="Blubb", author="Nicht die Mama", description="I don't know what I am doing. At least 50 chars...", owner=user1.id, modification_date=yesterday,
									long_description=lorem.paragraphs(2)))
	for tag in (".scenario", "race", "puzzle", "adventure", "melee"):
		packages[-1].tags.append(tags[tag])
	packages.append(models.Package(title="Larry", author="Kanibal", description="Database for mods (but it no work). At least 50 chars.", owner=user2.id, modification_date=yesterday,
									long_description=lorem.paragraphs(20)))
	for tag in ("advertisement", "test"):
		packages[-1].tags.append(tags[tag])
	packages.append(models.Package(title="Caedesblubb", author="Noone", description="Bundles Caedes and Blubb. At least 50 chars. At least 50 chars.", owner=user1.id, modification_date=last_week,
									long_description=lorem.paragraphs(1)))
	for tag in ("bundle", "openclonk-9", ".scenario", "test"):
		packages[-1].tags.append(tags[tag])
	for i in range(2):
		packages[-1].dependencies.append(models.PackageDependencies(packages[i]))
	packages.append(models.Package(title="戦争と平和",
		description="Unicode test. And also maximum description length test to see whether it looks fine in the interfaces because it should. Otherwise that would suck bad",
		owner=user2.id, modification_date=last_week))

	files = [os.path.join(models.app.config.get("TEST_DATA_PATH"), file) for file in os.listdir(models.app.config.get("TEST_DATA_PATH"))]

	with tempfile.TemporaryDirectory() as f:
		for idx, file in enumerate(files):
			target_file = f + "/" + file.split("/")[-1]
			shutil.copy(file, target_file)

			package = packages[int(idx/2)]
			res = models.Resource(package=package, owner=package.owner)
			session.add(res)
			try:
				res.init_from_path(target_file)
				print((target_file, res.sha1))
			except ValueError as e:
				print(str(e))
	session.commit()

	for p in packages:
		p.update_search_text()
		session.add(p)
	session.commit()