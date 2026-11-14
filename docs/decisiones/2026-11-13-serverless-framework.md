# D3: Serverless Framework como IaC

- Estado: aceptada
- Issue: #1

## Contexto
Necesitamos infraestructura como código para Lambdas, colas, tablas y Step Functions.

## Decisión
**Serverless Framework**, el que se usa en clase.

## Consecuencias
- **Un `serverless.yml` por servicio** (ej.: `services/reportes/serverless.yml`). Así cada zona de archivos tiene su propio stack y nadie edita el YAML de otro.
- Nombre del servicio: `telecorp-<dominio>`. Stage por parámetro: `serverless deploy --stage dev-<alias>`. Los recursos quedan como `telecorp-<dominio>-<stage>-...`.
- Región fija en el YAML: `provider.region: us-east-1`.
- Rol: siempre `LabRole` (ver [2026-11-13-aws-academy-us-east-1](2026-11-13-aws-academy-us-east-1.md)).
- **Step Functions**: con el plugin `serverless-step-functions`, indicando `role: arn:aws:iam::${aws:accountId}:role/LabRole` en cada máquina de estados.
- **Recursos compartidos entre servicios** (tablas, colas): los crea **un solo** servicio, que los publica como `Outputs` del stack de CloudFormation. Los demás los leen con `${cf:<stack>.<output>}`. **No se crea el mismo recurso en dos `serverless.yml`.**
- **Versión**: usar la misma que en clase y anotarla aquí. La v4 exige `serverless login` (cuenta gratuita); la v3 no.
  - Versión del equipo: `TODO` (completar al primer despliegue).
