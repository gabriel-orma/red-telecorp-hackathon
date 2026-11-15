"""Genera docs/arquitectura/arquitectura-red-telecorp.drawio (draw.io, íconos AWS4), por carriles de flujo. Uso: python scripts/generar-diagrama.py"""
import html
import itertools
import os

_id = itertools.count(2)
celdas = []
C = {"lambda": "#ED7100", "db": "#C925D1", "integ": "#E7157B", "sec": "#DD344C", "s3": "#7AA116", "mgmt": "#E7157B"}
RIESGO = "#D13212"


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


def lam(x, y, texto, riesgo=False):
    i = icono(x, y, "lambda", C["lambda"], texto)
    if riesgo:  # anillo rojo: punto de concurrencia
        celda("", f"ellipse;fillColor=none;strokeColor={RIESGO};strokeWidth=2;dashed=1;", x - 8, y - 8, 64, 64)
    return i


def caja(x, y, w, h, texto, relleno, borde, fuente=11, color_txt="#232F3E", negrita=1, alinear="left"):
    return celda(texto, f"rounded=1;arcSize=3;whiteSpace=wrap;html=1;fillColor={relleno};strokeColor={borde};fontSize={fuente};"
                        f"align={alinear};verticalAlign=top;spacingLeft=8;spacingTop=4;fontStyle={negrita};fontColor={color_txt};", x, y, w, h)


def externo(x, y, texto, relleno="#0078D4", borde="#005A9E"):
    return celda(texto, f"rounded=1;whiteSpace=wrap;html=1;fillColor={relleno};strokeColor={borde};fontColor=#FFFFFF;fontSize=10;fontStyle=1;",
                 x, y, 150, 50)


def flecha(a, b, texto="", guion=False, riesgo=False):
    color = RIESGO if riesgo else "#545B64"
    i = f"n{next(_id)}"
    celdas.append(f'<mxCell id="{i}" value="{esc(texto)}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;'
                  f'strokeWidth={2 if riesgo else 1.3};strokeColor={color};fontSize=9;fontColor={color};labelBackgroundColor=#ffffff;'
                  f'{"dashed=1;" if guion else ""}" edge="1" parent="1" source="{a}" target="{b}"><mxGeometry relative="1" as="geometry"/></mxCell>')


# ---------------- Marco ----------------
ANCHO = 2200
caja(20, 20, ANCHO - 40, 56, "Red TeleCorp · Arquitectura serverless en AWS Academy Learner Lab (us-east-1)", "#232F3E", "#232F3E", 16, "#FFFFFF", alinear="center")
celda("Despliegue: Serverless Framework v3 (IaC) · 4 stacks: base, antenas, api, workflows · scripts/deploy.sh · Rol: LabRole · "
      "54 Lambdas (Python 3.12) · 3 Step Functions · 8 tablas DynamoDB · 2 colas SQS (+ DLQ) · Cognito · S3 · SNS · SSM · Secrets Manager · 2.ª nube: Azure",
      "text;html=1;align=center;fontSize=11;fontColor=#545B64;", 20, 78, ANCHO - 40, 22)

# Encabezados de columna
cols = [(150, 230, "Entrada"), (390, 520, "Procesamiento (Lambda / SQS)"), (920, 250, "Datos"),
        (1180, 520, "Orquestación y eventos"), (1710, 170, "Salidas / 2.ª nube"), (1890, 290, "Concurrencia del carril")]
for x, w, t in cols:
    celda(t, "text;html=1;align=center;fontSize=12;fontStyle=1;fontColor=#232F3E;", x, 104, w, 20)

CARRILES = [
    ("1 · Consultas del panel y del portal", 130, 190),
    ("2 · Reporte de un ciudadano", 330, 190),
    ("3 · Métricas de las antenas", 530, 190),
    ("4 · Detección e incidente colectivo", 730, 240),
    ("5 · Tiempo real (WebSocket)", 980, 170),
    ("6 · Demo y tareas programadas", 1160, 200),
]
for titulo, y, h in CARRILES:
    caja(20, y, ANCHO - 40, h, titulo, "#FFFFFF", "#D5DBDB", 11)
    celda("", "rounded=1;arcSize=6;fillColor=#FFF4E5;strokeColor=#ED7100;", 1890, y + 8, 290, h - 16)

# ---------------- Carril 1: consultas ----------------
ope1 = icono(60, 175, "client", "#232F3E", "Operador NOC\n(panel web)")
apih = icono(200, 175, "api_gateway", C["integ"], "HTTP API (HTTPS)\n/api/* y frontend")
cog = icono(320, 175, "cognito", C["sec"], "Cognito\nJWT + grupo operadores")
web = lam(420, 175, "λ web → S3\n(frontend React)")
lect = lam(560, 175, "λ ×20 lecturas\nantenas, zonas, estado,\nanalítica, línea de tiempo")
admin = lam(720, 175, "λ ×8 operador\nestados, escenarios,\nsimulador, nubes")
s3 = icono(420, 260, "s3", C["s3"], "")
t_all = icono(1000, 175, "dynamodb", C["db"], "Lecturas de todas\nlas tablas")
flecha(ope1, apih, "HTTPS · polling 30 s\n(3 s sin WebSocket)", riesgo=True)
flecha(apih, cog, "valida JWT")
flecha(apih, web)
flecha(web, s3, guion=True)
flecha(apih, lect)
flecha(apih, admin)
flecha(lect, t_all, "Query/Scan")
nota1 = ("<b>1 Lambda por pedido HTTP en vuelo.</b><br>Cada pantalla pide 3–5 endpoints; con WebSocket se recargan al llegar avisos "
         "(throttle 0,7–2,5 s). Varios operadores/pestañas multiplican. <br><i>Línea de tiempo</i>: 1 Lambda que abre 16 hilos a DynamoDB.")

# ---------------- Carril 2: reportes ----------------
ciu = icono(60, 375, "users", "#232F3E", "Ciudadano\n(portal móvil)")
apih2 = icono(200, 375, "api_gateway", C["integ"], "HTTP API\nPOST /api/reportes")
pre = lam(320, 375, "λ preRegistro\n(Cognito PreSignUp)")
crear = lam(440, 375, "λ crearReporte\nvalida + dedup")
sqsr = icono(600, 375, "sqs", C["integ"], "SQS reportes\n(+ DLQ)")
regis = lam(760, 375, "λ registrarReporte\nbatch 10 · triage ML", riesgo=True)
tinc = icono(960, 375, "dynamodb", C["db"], "incidencias (stream)\n+ estadísticas + dedup")
flecha(ciu, apih2)
flecha(apih2, crear)
flecha(crear, sqsr, "encola")
flecha(sqsr, regis, "sin maximumConcurrency", riesgo=True)
flecha(regis, tinc)
nota2 = ("<b>⚠ SQS → Lambda escala sola</b> (empieza con ~5 lectores y sube si la cola crece). "
         "Una ráfaga de reportes (prueba de carga, escenarios) = varias Lambdas registrarReporte a la vez. "
         "Reintentos internos por conflictos de transacción alargan cada invocación.")

# ---------------- Carril 3: métricas ----------------
sch1 = icono(200, 575, "eventbridge", C["integ"], "Scheduler\nrate(1 minute)")
sim = lam(420, 575, "λ simulador\n4 lecturas/min × 36 antenas\nduerme entre lecturas (≤70 s)", riesgo=True)
sqsm = icono(600, 575, "sqs", C["integ"], "SQS métricas\n(+ DLQ)")
clas = lam(760, 575, "λ clasificador\nbatch 36 · ventana 1 s", riesgo=True)
tant = icono(960, 575, "dynamodb", C["db"], "antenas (stream)\nmétricas · historial")
flecha(sch1, sim, "cada minuto, siempre")
flecha(sim, sqsm, "144 msj/min")
flecha(sqsm, clas, "sin maximumConcurrency", riesgo=True)
flecha(clas, tant)
nota3 = ("<b>⚠ Carga constante 24/7 mientras el simulador esté encendido.</b> El simulador ocupa ~1 instancia casi todo el minuto "
         "y los escenarios lo invocan de nuevo (se solapa → 2). El clasificador recibe 144 mensajes/min → 1–3 instancias.")

# ---------------- Carril 4: detección ----------------
det = lam(1200, 790, "λ detector\nstreams incidencias + antenas\nbatch 20 · filtros")
rec = lam(1200, 890, "λ reconciliador\nrate(5 min)")
sfc = icono(1340, 790, "step_functions", C["integ"], "SFN incidente-colectivo\n1 ejecución por incidente\n(bucle de monitoreo)")
pasos = lam(1520, 790, "λ ×12 pasos\nverificar, priorizar, resumir,\nconfirmar, notificarLote…", riesgo=True)
ml = icono(960, 790, "lambda", C["lambda"], "Capa: modelo ML\npropio (0,3 MB)")
sns = icono(1720, 745, "sns", C["integ"], "SNS avisos +\nalertas NOC")
acs = externo(1720, 805, "Azure Communication\nServices (correo)")
maps = externo(1720, 862, "Azure Maps (clima)")
gem = externo(1720, 917, "Gemini API (opcional,\napagado)", "#5F6368", "#3C4043")
flecha(tinc, det, "stream INSERT")
flecha(tant, det, "stream: solo transición a falla")
flecha(det, sfc, "StartExecution")
flecha(rec, sfc, "reanuda zombis", guion=True)
flecha(sfc, pasos, "Task + Map ×5", riesgo=True)
flecha(pasos, sns)
flecha(pasos, acs)
flecha(pasos, maps)
flecha(pasos, gem, guion=True)
flecha(regis, ml, "triage de «OTRO»", guion=True)
nota4 = ("<b>⚠ Se multiplica por incidente abierto.</b> Cada incidente = 1 ejecución que llama Lambdas en cada paso y Map ×5 "
         "para avisar (hasta 5 Lambdas notificarLote a la vez por incidente). Monitoreo cada 30 s (4 s en la simulación acelerada). "
         "4 incidentes simultáneos → hasta ~20 Lambdas.")

# ---------------- Carril 5: tiempo real ----------------
difu = lam(1200, 1025, "λ difusor\n3 streams · batch 100", riesgo=True)
wsa = icono(1340, 1025, "api_gateway", C["integ"], "WebSocket API")
wsl = lam(1520, 1025, "λ ws ×3\nconectar / desconectar / ping")
tcon = icono(960, 1025, "dynamodb", C["db"], "colectivos (stream)\n+ conexiones")
ope2 = icono(1720, 1025, "client", "#232F3E", "Paneles abiertos")
flecha(tcon, difu, "stream")
flecha(difu, wsa, "post_to_connection")
flecha(wsa, ope2, "aviso {tipo}")
flecha(wsa, wsl, guion=True)
nota5 = ("<b>1 Lambda por stream y shard</b> (antenas, colectivos, incidencias) → ~3 constantes mientras haya cambios. "
         "Cada aviso hace que cada panel abierto vuelva a pedir datos al carril 1.")

# ---------------- Carril 6: demo y programadas ----------------
sfe = icono(1200, 1205, "step_functions", C["integ"], "SFN escenario\nMap ×1 + Wait (3–12 s)")
lese = lam(1340, 1205, "λ ×3 escenario\npreparar · oleada · finalizar")
sch2 = icono(200, 1205, "eventbridge", C["integ"], "Scheduler\ncron 06:00 Lima")
sfr = icono(1520, 1205, "step_functions", C["integ"], "SFN recurrencia\nMap ×5")
ssm = icono(960, 1205, "systems_manager", C["mgmt"], "SSM Parameter Store\nreglas · simulador · escenario")
secm = icono(1060, 1205, "secrets_manager", C["sec"], "Secrets Manager\nAzure · IA")
flecha(admin, sfe, "lanza escenario", guion=True)
flecha(sfe, lese)
flecha(lese, ssm, "fuerza fallas", guion=True)
flecha(lese, sqsr, "reportes simulados", riesgo=True)
flecha(sch2, sfr)
nota6 = ("<b>⚠ Un escenario dispara todos los carriles a la vez:</b> reportes (2), lecturas forzadas (3), incidentes (4) y avisos (5). "
         "Simulación acelerada: 60 oleadas cada 3 s, ~80 reportes y 4 incidentes en 3 min → pico estimado <b>35–50 Lambdas concurrentes</b>.")

for (titulo, y, h), texto in zip(CARRILES, [nota1, nota2, nota3, nota4, nota5, nota6]):
    i = f"n{next(_id)}"
    celdas.append(f'<mxCell id="{i}" value="{html.escape(texto, quote=True)}" style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;'
                  f'fontSize=10;fontColor=#232F3E;spacing=6;" vertex="1" parent="1"><mxGeometry x="1894" y="{y + 10}" width="282" height="{h - 20}" as="geometry"/></mxCell>')

# Leyenda
celda("<b>Leyenda</b>: flecha roja = punto donde se acumulan invocaciones en paralelo · círculo rojo = Lambda con riesgo de concurrencia · "
      "línea punteada = opcional / ocasional · CloudWatch: logs de todas las Lambdas + alarmas sobre las DLQ",
      "text;html=1;align=left;fontSize=10;fontColor=#545B64;", 20, 1372, ANCHO - 40, 22)

xml = ('<mxfile host="app.diagrams.net"><diagram id="arq" name="Arquitectura"><mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" '
       'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="2200" pageHeight="1400" math="0" shadow="0">'
       '<root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(celdas) + "</root></mxGraphModel></diagram></mxfile>")
salida = os.path.join(os.path.dirname(__file__), "..", "docs", "arquitectura", "arquitectura-red-telecorp.drawio")
os.makedirs(os.path.dirname(salida), exist_ok=True)
open(salida, "w", encoding="utf-8").write(xml)
print("ok", len(celdas))
