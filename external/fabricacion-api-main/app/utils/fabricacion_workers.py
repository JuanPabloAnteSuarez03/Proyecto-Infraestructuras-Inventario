import time
import httpx
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.core.config import API_PATH_INVENTARIO, MAX_WORKERS
from app.core.queue_fabricacion import fabricacion_queue


executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

#Worker
def worker_fabricacion(codigo:str, cantidad: int):
    url = API_PATH_INVENTARIO
    client = httpx.Client()
    for i in range(0, cantidad):
        time.sleep(1/24)
    
    data = {"codigo":codigo, "cantidad": cantidad}

    try:
        response = client.post(url, json=data)
        print(response.status_code)
    except Exception as e:
        print(f"[ERROR] Falló actualización inventario: {e}")
         
    client.close()
    
    print(f"[OK] Fabricado {codigo} -> pieza {cantidad}/{cantidad}")

def ejecutar_fabricacion(codigo: str, cantidad: int):

    # División del trabajo
    base = cantidad // MAX_WORKERS
    resto = cantidad % MAX_WORKERS

    cantidades_workers = [
        base + (1 if i < resto else 0)
        for i in range(MAX_WORKERS)
    ]

    print("Reparto entre workers:", cantidades_workers)

    futures = []

    for c in cantidades_workers:
        if c > 0:
            futures.append(
                executor.submit(worker_fabricacion, codigo, c)
            )

    # Esperar a que todos terminen
    for f in as_completed(futures):
        try:
            f.result()
        except Exception as e:
            print(f"[ERROR] en worker: {e}")

    print(">>> FABRICACIÓN COMPLETA <<<")


async def consumer_fabricacion():
    print(">>> Worker de fabricación iniciado...")
    loop = asyncio.get_event_loop()
    while True:
        job = await fabricacion_queue.get_job()
        codigo = job["codigo"]
        cantidad = job["cantidad"]

        print(f"[QUEUE] Procesando fabricación: {codigo} x {cantidad}")

        try:
            await loop.run_in_executor(
                None,
                ejecutar_fabricacion,
                codigo,
                cantidad
            )
        except Exception as e:
            print(f"[ERROR] en fabricación: {e}")

        fabricacion_queue.queue.task_done()