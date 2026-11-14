# D4: Python para todas las Lambdas

- Estado: aceptada
- Issue: #1

## Decisión
Todas las Lambdas en **Python**, con el runtime **`python3.12`** (verificar que Learner Lab lo soporte; si no, usar el más reciente disponible y actualizar aquí).

## Consecuencias
- AWS SDK: `boto3` (viene incluido en el runtime; no hace falta empaquetarlo).
- Dependencias extra por servicio en `requirements.txt`. Para empaquetarlas, usar `serverless-python-requirements` solo si hace falta.
- Pruebas con `pytest`, en `services/<dominio>/tests/`.
- Validación contra `contracts/` con la librería `jsonschema` si se necesita.
- Estilo: funciones cortas, un handler por archivo, docstrings en español.
