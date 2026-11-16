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


def externo(x, y, texto, relleno="#0078D4", borde="#005A9E", alto=50):
    return celda(texto, f"rounded=1;whiteSpace=wrap;html=1;fillColor={relleno};strokeColor={borde};fontColor=#FFFFFF;fontSize=10;fontStyle=1;",
                 x, y, 150, alto)


def flecha(a, b, texto="", guion=False, extra=""):
    i = f"n{next(_id)}"
    celdas.append(f'<mxCell id="{i}" value="{esc(texto)}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;'
                  f'strokeWidth=1.3;strokeColor=#545B64;fontSize=9;fontColor=#545B64;labelBackgroundColor=#ffffff;'
                  f'{"dashed=1;" if guion else ""}{extra}" edge="1" parent="1" source="{a}" target="{b}"><mxGeometry relative="1" as="geometry"/></mxCell>')



# ---------------- Marco ----------------
# Estilo: etiquetas cortas, sin párrafos y sin símbolos especiales (solo letras, números, + - / y paréntesis).
ANCHO = 2200
caja(20, 20, ANCHO - 40, 56, "Red TeleCorp - Arquitectura serverless multinube", "#232F3E", "#232F3E", 18, "#FFFFFF", alinear="center")
celda("AWS (principal) + Cloudflare (respaldo del estado) + Google Cloud (IA Gemini) + Azure (correo y clima)   |   "
      "Serverless Framework   |   Region us-east-1   |   Maximo 7 Lambdas a la vez",
      "text;html=1;align=center;fontSize=12;fontColor=#545B64;", 20, 78, ANCHO - 40, 22)

cols = [(150, 230, "Entrada"), (390, 520, "Procesamiento"), (920, 250, "Datos"),
        (1180, 520, "Orquestacion"), (1710, 170, "Otras nubes y salidas"), (1890, 290, "Resumen")]
for x, w, t in cols:
    celda(t, "text;html=1;align=center;fontSize=12;fontStyle=1;fontColor=#232F3E;", x, 104, w, 20)

CARRILES = [
    ("1. Panel del operador y frontend", 130, 190),
    ("2. Reporte de un usuario", 330, 190),
    ("3. Metricas de las antenas", 530, 190),
    ("4. Deteccion de incidente colectivo", 730, 240),
    ("5. Tiempo real", 980, 170),
    ("6. Tareas programadas y respaldo en Cloudflare", 1160, 200),
]
for titulo, y, h in CARRILES:
    caja(20, y, ANCHO - 40, h, titulo, "#FFFFFF", "#D5DBDB", 12)
    celda("", f"rounded=1;arcSize=6;fillColor=#EAF6EA;strokeColor={VERDE};", 1890, y + 8, 290, h - 16)

# ---------------- Carril 1 ----------------
ope1 = icono(60, 175, "client", "#232F3E", "Operador")
apih = icono(200, 175, "api_gateway", C["integ"], "API Gateway\n(HTTPS)")
cog = icono(320, 175, "cognito", C["sec"], "Cognito\n(login)")
s3 = icono(440, 255, "s3", C["s3"], "S3\n(frontend React)")
api = lam_tope(600, 175, "Lambda api\n(todas las rutas)", 2)
t_all = icono(1000, 175, "dynamodb", C["db"], "DynamoDB")
flecha(ope1, apih)
flecha(apih, cog)
flecha(apih, s3)
flecha(apih, api)
flecha(api, t_all, "lee")
nota1 = "<b>Panel y portal</b><br>- Una sola Lambda para la API<br>- La web sale de S3<br>- Si AWS falla: copia en Cloudflare"

# ---------------- Carril 2 ----------------
ciu = icono(60, 375, "users", "#232F3E", "Usuario\n(celular)")
apih2 = icono(200, 375, "api_gateway", C["integ"], "API Gateway")
pre = lam_tope(320, 375, "Lambda\nregistro de cuenta", 1)
api2 = lam_tope(440, 375, "Lambda api\nvalida reporte", 2, repetida=True)
sqsr = icono(600, 375, "sqs", C["integ"], "Cola SQS\nreportes")
seg = lam_tope(760, 375, "Lambda\nregistra + clasifica", 1)
tinc = icono(960, 375, "dynamodb", C["db"], "DynamoDB\nincidencias")
flecha(ciu, apih2, "reporta")
flecha(apih2, api2)
flecha(api2, sqsr, "encola")
flecha(sqsr, seg)
flecha(seg, tinc, "guarda")
nota2 = "<b>Reportes</b><br>- La cola absorbe los picos<br>- Ningun reporte se pierde<br>- IA propia clasifica el texto"

# ---------------- Carril 3 ----------------
sch1 = icono(200, 575, "eventbridge", C["integ"], "EventBridge\ncada minuto")
sim = lam_tope(420, 575, "Lambda\nsimulador", 1)
sqsm = icono(600, 575, "sqs", C["integ"], "Cola SQS\nmetricas")
clas = lam_tope(760, 575, "Lambda\nclasifica GB/min", 1, repetida=True)
tant = icono(960, 575, "dynamodb", C["db"], "DynamoDB\nantenas")
flecha(sch1, sim, "dispara")
flecha(sim, sqsm, "lecturas")
flecha(sqsm, clas)
flecha(clas, tant, "estado")
nota3 = "<b>Antenas</b><br>- 0 = inhabilitada<br>- menos de 60 = caida<br>- 60 a 129 = normal<br>- mas de 129 = saturada"

# ---------------- Carril 4 ----------------
mot = lam_tope(1200, 790, "Lambda detector", 2)
sfc = icono(1400, 790, "step_functions", C["integ"], "Step Functions\nciclo del incidente")
ml = icono(960, 790, "lambda", C["lambda"], "Modelo ML\npropio")
sns = icono(1720, 745, "sns", C["integ"], "SNS\navisos")
acs = externo(1720, 822, "Azure\ncorreo", alto=40)
maps = externo(1720, 868, "Azure Maps\nclima", alto=40)
gem = externo(1720, 914, "Google Cloud\nGemini (IA)", "#4285F4", "#1A5DC8", alto=40)
flecha(tinc, mot, "nuevo reporte")
flecha(tant, mot, "antena caida")
flecha(mot, sfc, "inicia")
flecha(sfc, mot, "cada paso", guion=True)
flecha(mot, sns)
LADO = "entryX=0;entryY=0.5;entryDx=0;entryDy=0;"   # entran por la izquierda: las flechas no cruzan las cajas
flecha(mot, acs, extra=LADO)
flecha(mot, maps, extra=LADO)
flecha(mot, gem, extra=LADO)
flecha(seg, ml, "clasifica", guion=True)
nota4 = ("<b>Incidente colectivo</b><br>- 10 usuarios, misma zona, menos de 24 h<br>- Prioriza por afectados y zona"
         "<br>- Avisa por app, SNS y correo<br>- IA sugiere causa")

# ---------------- Carril 5 ----------------
seg2 = lam_tope(1200, 1025, "Lambda\nenvia avisos", 1, repetida=True)
wsa = icono(1400, 1025, "api_gateway", C["integ"], "WebSocket")
tcon = icono(960, 1025, "dynamodb", C["db"], "DynamoDB\nincidentes")
ope2 = icono(1720, 1025, "client", "#232F3E", "Paneles abiertos")
flecha(tcon, seg2, "cambio")
flecha(seg2, wsa)
flecha(wsa, ope2, "actualiza")
nota5 = "<b>Tiempo real</b><br>- El panel se actualiza solo<br>- Sin recargar la pagina"

# ---------------- Carril 6 ----------------
sfe = icono(1200, 1205, "step_functions", C["integ"], "Step Functions\nescenarios demo")
sfr = icono(1400, 1205, "step_functions", C["integ"], "Step Functions\nrecurrencia diaria")
mot2 = lam_tope(1580, 1205, "Lambda detector\ncada 5 min", 2, repetida=True)
ssm = icono(960, 1205, "systems_manager", C["mgmt"], "SSM\nconfiguracion")
secm = icono(1100, 1205, "secrets_manager", C["sec"], "Secrets Manager\nclaves")
flecha(sfe, mot2)
flecha(sfr, mot2)
flecha(mot2, sqsr, "reportes de prueba", guion=True)
cf = externo(1720, 1205, "Cloudflare\nWorkers + KV", "#F38020", "#C2620A")
flecha(mot2, cf, "publica estado")
nota6 = ("<b>Concurrencia</b><br>- api 2, detector 2, otras 1 cada una<br>- Total 7 de 10 permitidas"
         "<br>- Cloudflare sigue en linea si AWS cae")

for (titulo, y, h), texto in zip(CARRILES, [nota1, nota2, nota3, nota4, nota5, nota6]):
    i = f"n{next(_id)}"
    celdas.append(f'<mxCell id="{i}" value="{html.escape(texto, quote=True)}" style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;'
                  f'fontSize=12;fontColor=#232F3E;spacing=8;" vertex="1" parent="1"><mxGeometry x="1894" y="{y + 10}" width="282" height="{h - 20}" as="geometry"/></mxCell>')

celda("<b>Leyenda</b>:   etiqueta verde = maximo de copias de la Lambda   |   recuadro punteado = misma Lambda en otro flujo   |   "
      "linea punteada = ocasional",
      "text;html=1;align=left;fontSize=11;fontColor=#545B64;", 20, 1372, ANCHO - 40, 22)

xml = ('<mxfile host="app.diagrams.net"><diagram id="arq" name="Arquitectura"><mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" '
       'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="2200" pageHeight="1400" math="0" shadow="0">'
       '<root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(celdas) + "</root></mxGraphModel></diagram></mxfile>")
salida = os.path.join(os.path.dirname(__file__), "..", "docs", "arquitectura", "arquitectura-red-telecorp.drawio")
os.makedirs(os.path.dirname(salida), exist_ok=True)
open(salida, "w", encoding="utf-8").write(xml)
print("ok", len(celdas))
