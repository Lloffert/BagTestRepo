import os
import sqlite3
from flask import current_app, g
import click

def _db_path():
    # store DB inside /instance, which Flask creates next to the package
    instance = current_app.instance_path
    os.makedirs(instance, exist_ok=True)
    return os.path.join(instance, current_app.config["DATABASE"])

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(_db_path(), detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        # enforce foreign keys
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db

def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    db.commit()

@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Initialized the database.")

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
