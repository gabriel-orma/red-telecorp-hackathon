# Verificación del Learner Lab (E0)

Stack de humo que crea un recurso mínimo de cada servicio con `LabRole` y una Lambda (`sonda`) que los prueba **con los permisos de LabRole**.

```bash
cd infra/verificacion
npx serverless deploy --stage humo
curl https://<api>/sonda        # JSON con ok/error por servicio
npx serverless remove --stage humo   # antes vacía el bucket versionado (ver bitácora E0)
```

Resultados de la última corrida: [D1](../../docs/decisiones/2026-11-13-aws-academy-us-east-1.md). Vuelve a correrlo si cambias de cuenta de lab.
