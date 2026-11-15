"""Genera docs/arquitectura/arquitectura-red-telecorp.drawio (draw.io, íconos AWS4), por carriles de flujo.

Refleja la decisión D14 (presupuesto de concurrencia: máximo 7 Lambdas a la vez). Uso: python scripts/generar-diagrama.py
"""
import html
import itertools
import os

_id = itertools.count(2)
celdas = []
C = {"lambda": "#ED7100", "db": "#C925D1", "integ": "#E7157B", "sec": "#DD344C", "s3": "#7AA116", "mgmt": "#E7157B"}
VERDE = "#1D8102"


def esc(t):
    return html.escape(t.replace(chr(10), "<br>"), quote=True)


def celda(valor, estilo, x, y, w, h):
    i = f"n{next(_id)}"
    celdas.append(f'<mxCell id="{i}" value="{esc(valor)}" style="{estilo}" vertex="1" parent="1">'
                  f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
    return i


def icono(x, y, res, color, texto):
    return celda(texto, f"sketch=0;outlineConnect=0;fontColor=#232F3E;fillColor={color};strokeColor=#ffffff;dashed=0;"
                        f"verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=10;aspect=fixed;"
                        f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};", x, y, 48, 48)


def lam_tope(x, y, texto, tope, repetida=False):
    """Lambda con su tope de concurrencia (reservedConcurrency) en una etiqueta verde."""
    i = icono(x, y, "lambda", C["lambda"], texto)
    if repetida:  # la misma función atendiendo otro flujo
        celda("", "rounded=1;fillColor=none;strokeColor=#ED7100;dashed=1;", x - 6, y - 6, 60, 60)
    celda(f"tope {tope}", f"rounded=1;arcSize=50;html=1;fillColor={VERDE};strokeColor=none;fontColor=#FFFFFF;fontSize=9;"
                          f"fontStyle=1;align=center;verticalAlign=middle;", x + 30, y - 12, 44, 18)
    return i


def caja(x, y, w, h, texto, relleno, borde, fuente=11, color_txt="#232F3E", negrita=1, alinear="left"):
    return celda(texto, f"rounded=1;arcSize=3;whiteSpace=wrap;html=1;fillColor={relleno};strokeColor={borde};fontSize={fuente};"
                        f"align={alinear};verticalAlign=top;spacingLeft=8;spacingTop=4;fontStyle={negrita};fontColor={color_txt};", x, y, w, h)


def externo(x, y, texto, relleno="#0078D4", borde="#005A9E"):
    return celda(texto, f"rounded=1;whiteSpace=wrap;html=1;fillColor={relleno};strokeColor={borde};fontColor=#FFFFFF;fontSize=10;fontStyle=1;",
                 x, y, 150, 50)


def flecha(a, b, texto="", guion=False):
    i = f"n{next(_id)}"
    celdas.append(f'<mxCell id="{i}" value="{esc(texto)}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;'
                  f'strokeWidth=1.3;strokeColor=#545B64;fontSize=9;fontColor=#545B64;labelBackgroundColor=#ffffff;'
                  f'{"dashed=1;" if guion else ""}" edge="1" parent="1" source="{a}" target="{b}"><mxGeometry relative="1" as="geometry"/></mxCell>')


# ---------------- Marco ----------------
ANCHO = 2200
caja(20, 20, ANCHO - 40, 56, "Red TeleCorp · Arquitectura serverless en AWS Academy Learner Lab (us-east-1) · "
     "presupuesto de concurrencia: 7 de 10 Lambdas", "#232F3E", "#232F3E", 16, "#FFFFFF", alinear="center")
celda("Despliegue: Serverless Framework v3 (IaC) · 4 stacks: base, antenas, api, workflows · scripts/deploy.sh · Rol: LabRole · "
      "5 Lambdas con tope (reservedConcurrency) · 3 Step Functions · 8 tablas DynamoDB · 2 colas SQS (+ DLQ) · Cognito · S3 · "
      "SNS · SSM · Secrets Manager · 2.ª nube: Azure",
      "text;html=1;align=center;fontSize=11;fontColor=#545B64;", 20, 78, ANCHO - 40, 22)

cols = [(150, 230, "Entrada"), (390, 520, "Procesamiento (Lambda / SQS)"), (920, 250, "Datos"),
        (1180, 520, "Orquestación y eventos"), (1710, 170, "Salidas / 2.ª nube"), (1890, 290, "Concurrencia (D14)")]
for x, w, t in cols:
    celda(t, "text;html=1;align=center;fontSize=12;fontStyle=1;fontColor=#232F3E;", x, 104, w, 20)

CARRILES = [
    ("1 · Panel, portal y frontend", 130, 190),
    ("2 · Reporte de un ciudadano", 330, 190),
    ("3 · Métricas de las antenas", 530, 190),
    ("4 · Detección e incidente colectivo", 730, 240),
    ("5 · Tiempo real (WebSocket)", 980, 170),
    ("6 · Demo y tareas programadas", 1160, 200),
]
for titulo, y, h in CARRILES:
    caja(20, y, ANCHO - 40, h, titulo, "#FFFFFF", "#D5DBDB", 11)
    celda("", f"rounded=1;arcSize=6;fillColor=#EAF6EA;strokeColor={VERDE};", 1890, y + 8, 290, h - 16)

# ---------------- Carril 1: panel, portal y frontend ----------------
ope1 = icono(60, 175, "client", "#232F3E", "Operador NOC\n(panel web)")
apih = icono(200, 175, "api_gateway", C["integ"], "HTTP API (HTTPS)\n/api/* y frontend")
cog = icono(320, 175, "cognito", C["sec"], "Cognito\nJWT + grupo operadores")
s3 = icono(440, 255, "s3", C["s3"], "S3 frontend\n(sin Lambda)")
api = lam_tope(600, 175, "λ api · router único\n26 rutas HTTP + WebSocket", 2)
t_all = icono(1000, 175, "dynamodb", C["db"], "Lecturas de todas\nlas tablas")
flecha(ope1, apih, "máx. 2 pedidos en vuelo\n+ reintento si «ocupado»")
flecha(apih, cog, "valida JWT")
flecha(apih, s3, "HTTP_PROXY: index.html, /assets/*")
flecha(apih, api, "/api/*")
flecha(api, t_all, "Query/Scan")
nota1 = ("<b>Tope 2.</b> Las 26 rutas comparten la misma función: si llegan más pedidos, API Gateway responde «ocupado» "
         "y el navegador reintenta. El frontend (index, JS, CSS, fuentes) <b>no usa Lambda</b>: va de S3 por el HTTP API.")

# ---------------- Carril 2: reporte de un ciudadano ----------------
ciu = icono(60, 375, "users", "#232F3E", "Ciudadano\n(portal móvil)")
apih2 = icono(200, 375, "api_gateway", C["integ"], "HTTP API\nPOST /api/reportes")
pre = lam_tope(320, 375, "λ preRegistro\n(Cognito PreSignUp)", 1)
api2 = lam_tope(440, 375, "λ api (misma)\nvalida + dedup", 2, repetida=True)
sqsr = icono(600, 375, "sqs", C["integ"], "SQS reportes (+ DLQ)\nvisibilidad 60 s · 20 intentos")
seg = lam_tope(760, 375, "λ segundoPlano\nregistrar · triage ML", 1)
tinc = icono(960, 375, "dynamodb", C["db"], "incidencias (stream)\n+ estadísticas + dedup")
flecha(ciu, apih2)
flecha(apih2, api2)
flecha(api2, sqsr, "encola")
flecha(sqsr, seg, "de a 1 lote")
flecha(seg, tinc)
nota2 = ("<b>Tope 1.</b> La cola SQS absorbe cualquier ráfaga (prueba de carga, escenarios): los reportes esperan su turno "
         "y se registran de a un lote. Si la función está ocupada el mensaje vuelve a la cola: nada se pierde.")

# ---------------- Carril 3: métricas ----------------
sch1 = icono(200, 575, "eventbridge", C["integ"], "Scheduler\nrate(1 minute)")
sim = lam_tope(420, 575, "λ simulador\nencola 4 lecturas con\nDelaySeconds 0/15/30/45", 1)
sqsm = icono(600, 575, "sqs", C["integ"], "SQS métricas\n(+ DLQ)")
clas = lam_tope(760, 575, "λ simulador (misma)\nclasifica · batch 36", 1, repetida=True)
tant = icono(960, 575, "dynamodb", C["db"], "antenas (stream)\nmétricas · historial")
flecha(sch1, sim, "cada minuto")
flecha(sim, sqsm, "termina en < 1 s")
flecha(sqsm, clas)
flecha(clas, tant)
nota3 = ("<b>Tope 1.</b> Simulador y clasificador son la misma función. El simulador ya no duerme dentro de la Lambda: "
         "SQS entrega cada muestra a su hora (retraso de 0, 15, 30 y 45 s).")

# ---------------- Carril 4: detección ----------------
mot = lam_tope(1200, 790, "λ detector · motor único\nstreams + barrido 5 min\n+ 17 pasos de Step Functions", 2)
sfc = icono(1400, 790, "step_functions", C["integ"], "SFN incidente-colectivo\nMap ×1 · reintento si\nel motor está ocupado")
ml = icono(960, 790, "lambda", C["lambda"], "Capa: modelo ML\npropio (0,3 MB)")
sns = icono(1720, 745, "sns", C["integ"], "SNS avisos +\nalertas NOC")
acs = externo(1720, 805, "Azure Communication\nServices (correo)")
maps = externo(1720, 862, "Azure Maps (clima)")
gem = externo(1720, 917, "Gemini API (opcional,\napagado)", "#5F6368", "#3C4043")
flecha(tinc, mot, "stream INSERT")
flecha(tant, mot, "stream: transición a falla")
flecha(mot, sfc, "StartExecution")
flecha(sfc, mot, "cada paso: {accion}", guion=True)
flecha(mot, sns)
flecha(mot, acs)
flecha(mot, maps)
flecha(mot, gem, guion=True)
flecha(seg, ml, "triage de «OTRO»", guion=True)
nota4 = ("<b>Tope 2.</b> Detector, barrido y los 17 pasos de las 3 Step Functions son UNA función. Cada tarea reintenta "
         "<i>Lambda.TooManyRequestsException</i> (hasta 40 veces con espera creciente) antes que cualquier otro error: "
         "si el motor está ocupado, el incidente espera; no falla.")

# ---------------- Carril 5: tiempo real ----------------
seg2 = lam_tope(1200, 1025, "λ segundoPlano (misma)\ndifusor · 3 streams", 1, repetida=True)
wsa = icono(1400, 1025, "api_gateway", C["integ"], "WebSocket API")
tcon = icono(960, 1025, "dynamodb", C["db"], "colectivos (stream)\n+ conexiones")
ope2 = icono(1720, 1025, "client", "#232F3E", "Paneles abiertos")
flecha(tcon, seg2, "stream")
flecha(seg2, wsa, "post_to_connection")
flecha(wsa, ope2, "aviso {tipo}")
nota5 = ("Los avisos comparten el tope 1 de segundo plano (si se atrasan, el panel igual se actualiza por su polling). "
         "$connect / $disconnect / ping usan el router (tope 2).")

# ---------------- Carril 6: demo y tareas programadas ----------------
sfe = icono(1200, 1205, "step_functions", C["integ"], "SFN escenario\nMap ×1 + Wait")
sfr = icono(1400, 1205, "step_functions", C["integ"], "SFN recurrencia\nMap ×1 (cron 06:00)")
mot2 = lam_tope(1580, 1205, "λ detector (misma)\npasos del escenario\ny de la recurrencia", 2, repetida=True)
ssm = icono(960, 1205, "systems_manager", C["mgmt"], "SSM Parameter Store\nreglas · simulador · escenario")
secm = icono(1060, 1205, "secrets_manager", C["sec"], "Secrets Manager\nAzure · IA")
flecha(sfe, mot2)
flecha(sfr, mot2)
flecha(mot2, sqsr, "reportes simulados", guion=True)
nota6 = ("<b>Total de la cuenta: api 2 + segundoPlano 1 + simulador 1 + detector 2 + preRegistro 1 = 7 de 10.</b> "
         "Quedan 3 para las Lambdas propias del laboratorio. Una prueba automática falla si una función no tiene tope "
         "o si la suma pasa de 7.")

for (titulo, y, h), texto in zip(CARRILES, [nota1, nota2, nota3, nota4, nota5, nota6]):
    i = f"n{next(_id)}"
    celdas.append(f'<mxCell id="{i}" value="{html.escape(texto, quote=True)}" style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;'
                  f'fontSize=10;fontColor=#232F3E;spacing=6;" vertex="1" parent="1"><mxGeometry x="1894" y="{y + 10}" width="282" height="{h - 20}" as="geometry"/></mxCell>')

celda("<b>Leyenda</b>: etiqueta verde = tope de concurrencia de la Lambda (reservedConcurrency) · recuadro punteado = la misma Lambda "
      "en otro flujo · línea punteada = opcional / ocasional · CloudWatch: logs + alarmas de las DLQ + métrica ConcurrentExecutions",
      "text;html=1;align=left;fontSize=10;fontColor=#545B64;", 20, 1372, ANCHO - 40, 22)

xml = ('<mxfile host="app.diagrams.net"><diagram id="arq" name="Arquitectura"><mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" '
       'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="2200" pageHeight="1400" math="0" shadow="0">'
       '<root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(celdas) + "</root></mxGraphModel></diagram></mxfile>")
salida = os.path.join(os.path.dirname(__file__), "..", "docs", "arquitectura", "arquitectura-red-telecorp.drawio")
os.makedirs(os.path.dirname(salida), exist_ok=True)
open(salida, "w", encoding="utf-8").write(xml)
print("ok", len(celdas))
