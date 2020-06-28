def init_database(drop=False):
    from . import models

    if drop:
        print("Dropping database...", flush=True)
        models.db.drop_all()

    print("Initializing database...", flush=True)
    models.db.create_all()
