import json
import uuid
import urllib.request
from datetime import datetime
import boto3

API_URL = "https://ultimosismo.igp.gob.pe/api/ultimo-sismo/ajaxb/{anio}"

def obtener(anio):
    req = urllib.request.Request(API_URL.format(anio=anio),
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data if isinstance(data, list) else data.get("data", [])

def clave_fecha(s):
    # Ordena por fecha + hora local; si no existen, por fecha UTC
    return f"{s.get('fecha_local') or s.get('fecha_utc') or ''} {s.get('hora_local') or s.get('hora_utc') or ''}"

def lambda_handler(event, context):
    anio = datetime.utcnow().year
    sismos = obtener(anio)
    if len(sismos) < 10:                 # inicio de año: completa con el año anterior
        sismos += obtener(anio - 1)

    ultimos = sorted(sismos, key=clave_fecha, reverse=True)[:10]

    table = boto3.resource("dynamodb").Table("TablaSismosIGP")

    # Borra los datos anteriores para que la tabla tenga solo los 10 últimos
    scan = table.scan()
    with table.batch_writer() as batch:
        for item in scan.get("Items", []):
            batch.delete_item(Key={"id": item["id"]})

    resultado = []
    for i, s in enumerate(ultimos, start=1):
        # Todo como string: DynamoDB no acepta float
        item = {k: str(v) for k, v in s.items() if v is not None}
        item["id"] = str(uuid.uuid4())
        item["#"] = i
        table.put_item(Item=item)
        resultado.append(item)

    return {"statusCode": 200, "body": resultado}
