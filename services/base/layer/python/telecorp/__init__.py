"""Código compartido por todas las Lambdas de Red TeleCorp (se publica como Lambda Layer `comun`).

- util: fechas, ids y conversión de tipos de DynamoDB.
- reglas: lógica de negocio pura (clasificación, transiciones). Sin AWS: se prueba con pytest.
- zonas: catálogo de zonas y antenas (copia de contracts/zonas.json hecha por scripts/deploy.sh).
- config: parámetros de SSM (/telecorp/<stage>/...) con caché.
- db: acceso a las tablas por nombre lógico.
- historial: registro de eventos inmutables (contracts/schemas/evento-historial.schema.json).
- http: respuestas JSON del API.
"""
