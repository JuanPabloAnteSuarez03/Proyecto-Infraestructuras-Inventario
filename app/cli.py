import click
import httpx
import os
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


@cli.command("test-fabrica")
def test_fabrica_command():
    """Probar conexión con la fábrica externa."""
    base_url = os.getenv("FABRICA_BASE_URL", "").rstrip("/")

    if not base_url:
        click.echo("❌ Error: FABRICA_BASE_URL no está configurada en .env")
        return

    click.echo(f"Probando conexión con: {base_url}")
    click.echo()

    # Probar endpoint raíz
    click.echo("1. Probando endpoint raíz...")
    try:
        resp = httpx.get(base_url, timeout=10)
        click.echo(f"   ✓ Status: {resp.status_code}")
    except Exception as e:
        click.echo(f"   ✗ Error: {e}")
        return

    # Probar documentación
    click.echo()
    click.echo("2. Probando documentación (/docs)...")
    try:
        resp = httpx.get(f"{base_url}/docs", timeout=10)
        click.echo(f"   ✓ Status: {resp.status_code}")
        click.echo(f"   ✓ Documentación disponible en: {base_url}/docs")
    except Exception as e:
        click.echo(f"   ✗ Error: {e}")

    # Probar planos
    click.echo()
    click.echo("3. Probando planos de fabricación...")
    planos = {1: "S1", 2: "S2"}
    for plano_id, codigo in planos.items():
        try:
            resp = httpx.get(f"{base_url}/fabricacion/planos/{plano_id}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                click.echo(f"   ✓ Plano {codigo}: disponible")
                click.echo(f"     - Nombre: {data.get('nombre', 'N/A')}")
                click.echo(f"     - Tiempo: {data.get('tiempo_fabricacion', 'N/A')} minutos")
            else:
                click.echo(f"   ✗ Plano {codigo}: status {resp.status_code}")
        except Exception as e:
            click.echo(f"   ✗ Plano {codigo}: {e}")

    # Probar cálculo de piezas
    click.echo()
    click.echo("4. Probando cálculo de piezas...")

    # Probar diferentes formatos de código
    test_codes = [("S1", 100), ("S2", 50)]
    for codigo, cantidad in test_codes:
        try:
            resp = httpx.post(
                f"{base_url}/fabricacion/calculo_piezas",
                json={"codigo": codigo, "cantidad": cantidad},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                click.echo(f"   ✓ {codigo} x {cantidad}:")
                for pieza in data.get("piezas", []):
                    click.echo(f"     - {pieza.get('codigo_pieza')}: {pieza.get('total_piezas')} unidades")
            else:
                click.echo(f"   ✗ {codigo}: status {resp.status_code} - {resp.text[:100]}")
        except Exception as e:
            click.echo(f"   ✗ {codigo}: {e}")

    click.echo()
    click.echo("✓ Pruebas completadas")


if __name__ == "__main__":
    cli()
