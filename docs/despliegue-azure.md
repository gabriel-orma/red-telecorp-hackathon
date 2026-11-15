# Despliegue de la segunda nube (Azure)

Red TeleCorp usa **dos servicios de Azure** desde las Lambdas de AWS: **Communication Services** (correo de los avisos) y **Azure Maps** (clima de la zona del incidente). Esta guía crea esos recursos y entrega sus claves a AWS **sin guardarlas en el repo**.

## Qué se crea
| Recurso | Tipo | Configuración |
|---|---|---|
| Grupo de recursos | `Microsoft.Resources` | región permitida por la política de la suscripción (en la nuestra, `northcentralus`) |
| Azure Maps | `Microsoft.Maps/accounts` | SKU `G2`, `Gen2`, ubicación **`global`** |
| Communication Services | `Microsoft.Communication/communicationServices` | ubicación **`global`**, `--data-location unitedstates` |
| Email Communication Service | `…/emailServices` | ubicación **`global`**, `--data-location unitedstates` |
| Dominio de correo | `…/emailServices/domains` | `AzureManagedDomain` (gestionado por Azure: SPF y DKIM quedan verificados solos), **enlazado** al Communication Services |

## Permisos y dependencias
**Azure**
- Rol **Contributor** (o Owner) sobre el grupo de recursos, y poder registrar los proveedores `Microsoft.Communication` y `Microsoft.Maps` (`az provider register -n …`; en nuestra suscripción ya estaban registrados).
- **Azure for Students (UTEC):** una política «Allowed locations», asignada en un grupo de administración que el alumno no puede leer ni modificar, **deniega los recursos regionales**; los de ubicación `global` sí se crean. Por eso todo va en `global`. **No se debe intentar eludir la política.** En otra suscripción sin esa política también funciona.
- Dependencia de orden: Communication Services necesita el dominio de correo ya creado para poder enlazarlo.

**AWS**
- `LabRole` ya puede leer Secrets Manager y las Lambdas **no están en una VPC**, así que tienen salida a internet (no hace falta NAT Gateway: costaría por hora).
- Hosts HTTPS a los que salen las Lambdas: `<recurso>.unitedstates.communication.azure.com` (correo), `atlas.microsoft.com` (clima) y, si se activa, `generativelanguage.googleapis.com` (Gemini).

## Pasos
```bash
az login                                   # o la sesión que uses
az group create -n rg-telecorp -l northcentralus
az provider register -n Microsoft.Communication && az provider register -n Microsoft.Maps

SUF=$RANDOM                                # los nombres deben ser únicos
az maps account create -n tcmaps$SUF -g rg-telecorp --sku G2 --kind Gen2 -l global --accept-tos
az communication create -n tccomm$SUF -g rg-telecorp -l global --data-location unitedstates
az communication email create -n tcemail$SUF -g rg-telecorp -l global --data-location unitedstates
az communication email domain create --domain-name AzureManagedDomain --email-service-name tcemail$SUF \
   -g rg-telecorp -l global --domain-management AzureManaged

DOMINIO_ID=$(az communication email domain show --domain-name AzureManagedDomain --email-service-name tcemail$SUF -g rg-telecorp --query id -o tsv)
az communication update -n tccomm$SUF -g rg-telecorp --linked-domains "$DOMINIO_ID"
```

## Entregar las claves a AWS (Secrets Manager)
```bash
bash scripts/azure-secreto.sh <stage> rg-telecorp tccomm$SUF tcemail$SUF tcmaps$SUF "correo1@dominio,@otrodominio"
```
Crea o actualiza `telecorp/<stage>/azure` con `{acsEndpoint, acsKey, acsSender, mapsKey, destinatarios}`. **No imprime ningún valor.** Al actualizar conserva la lista `destinatarios` si no pasas una nueva.

**Destinatarios autorizados:** las cuentas de Cognito se auto-verifican (D9); sin una barrera, cualquiera podría hacer que el remitente escriba a un tercero. Por eso el sistema **solo envía a la lista `destinatarios`** y, sin lista, no envía por Azure (los avisos siguen por la app y SNS). En producción habría que verificar el correo en Cognito.

## Comprobar que funciona
1. Desplegar el stage (`bash scripts/deploy.sh <stage>`).
2. Con una sesión de operador: `GET /api/nubes` → `azure.acsEmail` y `azure.maps` en `OK` (mide con operaciones reales; **no envía correo**).
3. Flujo real: 10 usuarios reportan en una zona con un destinatario autorizado → Step Functions → clima de Maps en el análisis → correo por ACS. El historial guarda el id de operación de ACS; su entrega se comprueba con `GET /emails/operations/{id}` (`Succeeded`).

## Límites y costos
- Dominio administrado por Azure: **5 correos/min y 10/h** (el código respeta 5/min y 8/h; si se agota, el aviso sale por SNS y la app).
- Azure Maps Gen2: el clima se cachea 10 min por zona y las sondas del panel se limitan a una cada 5 min.
- Todo es por uso; no hay recursos encendidos 24/7.

## Seguridad
- Las claves viven **solo** en Secrets Manager (`telecorp/<stage>/azure`), nunca en el repo, los logs ni las variables de entorno de las Lambdas.
- Para rotarlas: regenerar la clave en Azure (`az communication regenerate-key`, `az maps account keys renew`) y volver a ejecutar `scripts/azure-secreto.sh`.
- Para borrar todo: `az group delete -n rg-telecorp` (solo si el grupo es exclusivo de este proyecto).
