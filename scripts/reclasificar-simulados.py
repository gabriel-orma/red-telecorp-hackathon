"""Marca como SIMULADOS los incidentes colectivos antiguos que nacieron de datos de demo (D13).

Antes de la separación de datos simulados y operativos (decisión D13) los colectivos no llevaban la marca `simulado`. Este script
revisa los colectivos sin marca y, si TODAS sus incidencias son simuladas (`reporte.simulado`), les pone `simulado: true` y deja una nota
en su historial. No borra nada ni toca colectivos con incidencias reales. Los que no tienen incidencias (nacidos solo por una antena) no se
pueden clasificar con seguridad y se listan aparte.

Por defecto es un SIMULACRO (solo informa). Hay que pasar `--aplicar` para escribir.

Uso (requiere credenciales de AWS):
  python scripts/reclasificar-simulados.py dev-rodrigo            # informe
  python scripts/reclasificar-simulados.py dev-rodrigo --aplicar  # marca los candidatos

Límite: los contadores de estadísticas y el historial de antenas anteriores a D13 son agregados y no se pueden separar.
"""
import argparse
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("stage")
    ap.add_argument("--aplicar", action="store_true", help="escribe la marca (sin esto solo informa)")
    args = ap.parse_args()

    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    colectivos = ddb.Table(f"telecorp-{args.stage}-colectivos")
    incidencias = ddb.Table(f"telecorp-{args.stage}-incidencias")
    historial = ddb.Table(f"telecorp-{args.stage}-historial")

    items, kw = [], {"FilterExpression": Attr("simulado").not_exists()}
    while True:
        r = colectivos.scan(**kw)
        items += r["Items"]
        if "LastEvaluatedKey" not in r:
            break
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]

    candidatos, reales, sin_clasificar = [], [], []
    for c in items:
        ids = c.get("incidencias", [])
        if not ids:
            sin_clasificar.append(c["incidenteColectivoId"])
            continue
        simuladas = 0
        for iid in ids:
            inc = incidencias.get_item(Key={"incidenciaId": iid}).get("Item")
            if inc and (inc.get("reporte") or {}).get("simulado"):
                simuladas += 1
        (candidatos if simuladas == len(ids) else reales).append(c["incidenteColectivoId"])

    print(f"Colectivos sin marca: {len(items)}")
    print(f"  · todas sus incidencias son simuladas (se marcarían): {len(candidatos)}")
    print(f"  · con incidencias reales o mezcladas (se dejan como operativos): {len(reales)}")
    print(f"  · sin incidencias, no clasificables: {len(sin_clasificar)}")
    if not args.aplicar:
        print("\nSimulacro: no se escribió nada. Usa --aplicar para marcar los candidatos.")
        return
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for cid in candidatos:
        colectivos.update_item(Key={"incidenteColectivoId": cid}, UpdateExpression="SET simulado = :v",
                               ExpressionAttributeValues={":v": True})
        historial.put_item(Item={"entidadId": cid, "sk": f"{ahora}#COMENTARIO#reclasif", "entidadTipo": "INCIDENTE_COLECTIVO",
                                 "ocurridoEn": ahora, "tipoEvento": "COMENTARIO", "actor": "SISTEMA", "simulado": True,
                                 "detalle": "Reclasificado como simulado (todas sus incidencias eran de simulación)",
                                 "estadoAnterior": None, "estadoNuevo": None},
                           ConditionExpression="attribute_not_exists(sk)")
    print(f"\nMarcados como simulados: {len(candidatos)}")


if __name__ == "__main__":
    main()
