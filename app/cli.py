from flask.cli import with_appcontext
import click
from .extensions import db
from .services.seed_service import load_seed_data


def register_cli(app):
    @app.cli.command("create-db")
    @with_appcontext
    def create_db_command():
        """Create database tables."""
        db.create_all()
        click.echo("Tablas creadas correctamente")

    @app.cli.command("seed-db")
    @with_appcontext
    def seed_db_command():
        """Populate the database from JSON seed files."""
        load_seed_data()
        click.echo("Datos de ejemplo cargados")
