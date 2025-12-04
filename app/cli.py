import click
from .database import Base, engine, SessionLocal
from .services.seed_service import load_seed_data
from .models.entities import InventarioProducto, InventarioPieza


@click.group()
def cli():
    """Comandos utilitarios para la base de datos."""
    pass


@cli.command("create-db")
def create_db_command():
    """Crear tablas en la base de datos configurada."""
    Base.metadata.create_all(bind=engine)
    click.echo("Tablas creadas correctamente")


@cli.command("seed-db")
def seed_db_command():
    """Cargar datos de ejemplo desde JSON."""
    with SessionLocal() as session:
        load_seed_data(session)
    click.echo("Datos de ejemplo cargados")


@cli.command("reset-inventory")
def reset_inventory_command():
    """Resetear todo el inventario de productos y piezas a cero."""
    with SessionLocal() as session:
        # Resetear inventario de productos
        productos_count = session.query(InventarioProducto).update({"cantidad": 0})

        # Resetear inventario de piezas
        piezas_count = session.query(InventarioPieza).update({"cantidad": 0})

        session.commit()

        click.echo(f"Inventario reseteado correctamente:")
        click.echo(f"  - {productos_count} productos actualizados")
        click.echo(f"  - {piezas_count} piezas actualizadas")


if __name__ == "__main__":
    cli()
