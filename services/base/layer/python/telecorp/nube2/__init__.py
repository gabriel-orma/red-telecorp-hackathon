"""Integraciones con la 2.ª nube y la IA (Azure, Google Cloud). Solo biblioteca estándar + boto3/botocore.

Principios (AGENTS.md R2/R3/R5):
- Las reglas críticas de telecomunicaciones NO viven aquí: la IA y las nubes enriquecen, nunca deciden umbrales.
- Toda función pública devuelve un resultado estructurado o `None`; NUNCA propaga una excepción al flujo del negocio.
- Los secretos se leen de AWS Secrets Manager (`telecorp/<stage>/<azure|gcp|ia>`) y jamás se registran en logs.
- La frontera HTTP es una sola (`http_cliente.transporte`): las pruebas la sustituyen; no hay otra salida a red.
"""
