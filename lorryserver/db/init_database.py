def init_database(drop=False):
    from .. import app
    from . import models

    with app.app_context():
        if drop:
            print("Dropping database...", flush=True)
            models.db.drop_all()

        print("Initializing database...", flush=True)
        models.db.create_all()
