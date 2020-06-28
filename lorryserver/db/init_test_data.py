import shutil
import tempfile
import os

def init_test_data():
	from . import models
	session = models.db.session
	print("Filling database with test data...", flush=True)

	user1 = models.User(name="Larrytest", email="larry@larry.larry", password="$pbkdf2-sha256$30000$CmEMYSwlJMQYg1DKOQdAyA$gEJpG8kZwlryp1zrAyD0E6a1dYOuCBIhierWyx9LjyA")
	user2 = models.User(name="Larry", password="$pbkdf2-sha256$30000$iZFSqjWGcA7B.H.PMcY45w$V6H/tiV.wHlKfv.u2WtDNCEocl56wYE3FHMVEMWdd98")

	session.add(user1)
	session.add(user2)
	session.commit()

	tags = dict()
	for tag in ("openclonk-9", ".ocs", ".ocd", ".ocf", "multiplayer", "advertisement", "bundle"):
		t = models.Tag(title=tag)
		tags[tag] = t
		session.add(t)
	session.commit()

	packages = []
	packages.append(models.Package(title="Caedes", author="Zapper, KKenny", description="The very first and the very last.", owner=user1.id))
	for tag in ("openclonk-9", ".ocd", ".ocf", ".ocs", "multiplayer"):
		packages[-1].tags.append(tags[tag])
	packages.append(models.Package(title="Blubb", author="Nicht die Mama", description="I don't know what I am doing.", owner=user1.id))
	for tag in (".ocs",):
		packages[-1].tags.append(tags[tag])
	packages.append(models.Package(title="Larry", author="Kanibal", description="Database for mods (but it no work).", owner=user1.id))
	for tag in ("advertisement",):
		packages[-1].tags.append(tags[tag])
	packages.append(models.Package(title="Caedesblubb", author="Noone", description="Bundles Caedes and Blubb.", owner=user2.id))
	for tag in ("bundle", "openclonk-9", ".ocf"):
		packages[-1].tags.append(tags[tag])
	for i in range(2):
		packages[-1].dependencies.append(models.PackageDependencies(packages[i]))
	packages.append(models.Package(title="戦争と平和", description="Unicode test.", owner=user2.id))

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
			except ValueError as e:
				print(str(e))
	session.commit()

	for p in packages:
		p.update_search_text()
		session.add(p)
	session.commit()