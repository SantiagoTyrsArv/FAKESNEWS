# Operación en Azure

Runbook de la API de FakesNews en Azure (desde el 2026-11-04). El diseño está en
[superpowers/specs/2026-11-04-azure-migration-design.md](superpowers/specs/2026-11-04-azure-migration-design.md)
y el plan de la migración, en [superpowers/plans/2026-11-04-azure-migration.md](superpowers/plans/2026-11-04-azure-migration.md).

Los comandos son para Git Bash con el CLI de Azure (`az login` con la cuenta de Azure for Students).
En Git Bash, los scripts de `infra/scripts/` se lanzan con `MSYS_NO_PATHCONV=1` delante, para que
no reescriba las rutas que se le pasan a `az`.

## Recursos

Todo está en el grupo de recursos `rg-fakesnews-prod` (`northcentralus`). La política de la
suscripción solo permite `brazilsouth`, `northcentralus`, `canadacentral`, `chilecentral` y
`spaincentral`.

| Recurso | Nombre | Notas |
|---|---|---|
| API | `ca-fakesnews-api` | `https://ca-fakesnews-api.proudpebble-539cdba7.northcentralus.azurecontainerapps.io`. Siempre 1 réplica (en frío tardaba 30 s), máximo 2 |
| Worker | `ca-fakesnews-worker` | Escala de 0 a 1 con KEDA `postgresql`: se enciende si hay envíos sin terminar de los últimos 20 min y se apaga 300 s después |
| Redis | `ca-fakesnews-redis` | `redis:7-alpine`, TCP interno 6379, sin disco (solo datos temporales) |
| Migraciones | `caj-fakesnews-migrate` | Job manual: `alembic upgrade head` |
| PostgreSQL | `psql-fakesnews` | Flexible Server 18, B1ms, 32 GB, acceso privado, backups de 7 días |
| Secretos | `kv-fakesnews-4q4yxz5r` | RBAC. Las apps leen con `id-fakesnews-apps` |
| Storage | `stfakesnews4q4yxz5r` | Shares `whisper-cache` (montado en `~/.cache` del worker) y `pgdump` |
| Logs | `log-fakesnews` | 30 días, tope de 0,15 GB al día |
| Presupuesto | `budget-fakesnews-monthly` | 10 USD al mes, con aviso por correo al 80 % y al 100 % |
| Identidad de despliegue | `id-fakesnews-deploy` | Contributor en el grupo de recursos. Su credencial federada solo vale para `main` |

## Desplegar

- **La app:** cada push a `main` que toca `apps/api/` ejecuta `api-deploy.yml`:
  1. construye `ghcr.io/santiagotyrsarv/fakesnews-api:<sha>`;
  2. ejecuta el job de migraciones;
  3. si las migraciones terminan bien, actualiza la API y el worker.

  Para relanzarlo a mano: `gh workflow run api-deploy.yml`.
- **La infraestructura:** cada push a `main` que toca `infra/` ejecuta `infra.yml`, que despliega
  `infra/main.bicep` conservando la imagen en uso. Los dos workflows comparten el grupo de
  `concurrency` `azure-deploy` y nunca se ejecutan a la vez.
- **`infra/bootstrap.bicep`** (identidades, roles y Key Vault) se despliega a mano y solo cuando
  cambia, porque la identidad de despliegue no puede asignar roles:

  ```bash
  az deployment group create -g rg-fakesnews-prod -n bootstrap -f infra/bootstrap.bicep \
    -p adminObjectId=$(az ad signed-in-user show --query id -o tsv)
  ```

- Antes de desplegar algo a mano, revisa los cambios con
  `az deployment group what-if -g rg-fakesnews-prod -f infra/main.bicep -p infra/main.bicepparam`.

## Volver a una versión anterior

```bash
az containerapp update -g rg-fakesnews-prod -n ca-fakesnews-api --image ghcr.io/santiagotyrsarv/fakesnews-api:<sha-anterior>
az containerapp update -g rg-fakesnews-prod -n ca-fakesnews-worker --image ghcr.io/santiagotyrsarv/fakesnews-api:<sha-anterior>
```

Las migraciones no se deshacen solas. Si la versión nueva traía una migración, hay que bajarla
antes con `alembic downgrade`, desde el job de migraciones y cambiándole el comando.

## Ver logs

```bash
az containerapp logs show -g rg-fakesnews-prod -n ca-fakesnews-api --tail 50
az containerapp logs show -g rg-fakesnews-prod -n ca-fakesnews-worker --type system --tail 50   # escalado, KEDA
```

Para consultas, usa Log Analytics (`log-fakesnews`), tabla `ContainerAppConsoleLogs_CL`. Por
ejemplo, los 5xx de la última hora:

```kusto
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "ca-fakesnews-api" and TimeGenerated > ago(1h)
| extend s = toint(extract("\"status\": ([0-9]+)", 1, Log_s))
| where s >= 500
```

## Base de datos

Postgres no tiene acceso público. Para consultarla, usa `infra/scripts/psql-job.sh`, que lanza
`psql` en un job dentro del entorno:

```bash
MSYS_NO_PATHCONV=1 infra/scripts/psql-job.sh "select count(*) from users"
```

- **Migraciones a mano:** `az containerapp job start -g rg-fakesnews-prod -n caj-fakesnews-migrate`.
- **Restaurar un backup** (point-in-time, últimos 7 días): crea un servidor nuevo y apunta la app
  a él.
  1. Ejecuta
     `az postgres flexible-server restore -g rg-fakesnews-prod --name psql-fakesnews-restored --source-server psql-fakesnews --restore-time "<ISO 8601 UTC>"`.
  2. Actualiza los secretos `database-url`, `database-url-app` y `keda-pg-connection` con el FQDN nuevo.
     El rol `fakesnews_app` viaja con el backup.
  3. Reinicia la API y el worker.
- **Comparar dos bases:** `infra/scripts/row-counts.sql` devuelve el número de filas de cada tabla
  y la revisión de alembic.

## Secretos

**Postgres tiene dos logins.** La API y el worker usan `database-url-app`, con el rol
`fakesnews_app`: puede leer y escribir filas, pero no crear ni cambiar tablas. El job de
migraciones, KEDA y `psql-job.sh` usan el administrador (`fakesnews_admin`, en `database-url` y
`keda-pg-connection`). Los privilegios por defecto dan a `fakesnews_app` acceso a las tablas que
creen las migraciones futuras, siempre que las cree `fakesnews_admin`.

Están en Key Vault, nunca en el repo ni en GitHub: `database-url`, `database-url-app`,
`keda-pg-connection`, `redis-url`, `redis-password`, `jwt-secret-key`, `totp-secret-encryption-key`, `gemini-api-key`,
`tavily-api-key`, `api-proxy-secret` y `pg-admin-password`.

Para rotar uno:
1. Guarda el valor nuevo en un archivo temporal y súbelo desde ahí, no con `--value`, que lo deja
   en el historial del shell y en la lista de procesos mientras corre:
   ```
   read -rs NUEVO && printf %s "$NUEVO" > /tmp/secreto && unset NUEVO
   az keyvault secret set --vault-name kv-fakesnews-4q4yxz5r -n <nombre> --file /tmp/secreto --encoding utf-8 -o none
   rm /tmp/secreto
   ```
2. Reinicia la revisión de las apps que lo usan:
   `az containerapp revision restart -g rg-fakesnews-prod -n <app> --revision <revisión>`.
   Las referencias a Key Vault también se refrescan solas, cada 30 minutos aproximadamente.

Antes de rotar, ten en cuenta estos:
- `gemini-api-key`: debe ser de un proyecto sin facturación, o dejará de funcionar el plan gratuito.
- `jwt-secret-key`: cierra todas las sesiones.
- `totp-secret-encryption-key`: deja inservibles los secretos TOTP cifrados, y nadie con 2FA podría
  entrar.
- `api-proxy-secret`: hay que cambiarlo a la vez en Vercel (`API_PROXY_SECRET`).

## Observabilidad

Diseño: [especificación](superpowers/specs/2026-11-09-observability-design.md).

### Alerta de errores (`alert-fakesnews-errors`)

- **Qué vigila:** cada hora busca en los logs de la API y del worker las líneas JSON con
  `level: error` o el aviso `submissions_marked_stuck`:
  - de cuota: `search_quota_exhausted`, `llm_quota_exhausted` y `verification_quota_exhausted`;
  - del pipeline: `run_pipeline_failed`, `run_pipeline_cancelled` y
    `run_pipeline_submission_not_found`;
  - otros: `unhandled_error`, `submission_enqueue_failed`, `verify_claim_no_trusted_sources` y
    `password_hash_unreadable`.
- **Qué no vigila:** las trazas de texto plano del worker al apagarse (`Error 111 connecting to
  ca-fakesnews-redis`), que son ruido.
- **A quién avisa:** al correo del presupuesto, a través del grupo de acciones
  `ag-fakesnews-email`. Después calla 6 horas aunque el problema siga.
- **Qué hacer con un aviso:** el correo enlaza a la consulta, que dice qué evento y cuántas
  veces. Para ver el contexto, usa «Errores por evento» y «Ciclo de vida de un caso» (abajo).
  - **Cuota agotada:** Tavily se renueva el día 1 de cada mes; Gemini, a diario hacia las
    08:00 UTC.
  - **`unhandled_error`:** la traza está en el campo `exception`.
- **Coste:** 0,50 USD al mes.
- **Identidad:** la consulta corre con `id-fakesnews-alerts`, que solo tiene «Log Analytics Reader»
  sobre el grupo de recursos. Se crea en `bootstrap.bicep`.
- **Silenciarla:**
  `az resource update -g rg-fakesnews-prod -n alert-fakesnews-errors --resource-type Microsoft.Insights/scheduledQueryRules --set properties.enabled=false`,
  y `properties.enabled=true` para volver a activarla. El siguiente despliegue de `infra.yml` la vuelve a
  activar.

### Sondeo de disponibilidad (`uptime.yml`)

- **Qué hace:** cada 6 horas comprueba desde GitHub Actions que `https://fakesnews.vercel.app/` y
  `/api/health/ready` responden. Cada petición tiene 90 s de tiempo máximo y un reintento al
  minuto, porque un arranque en frío tarda unos 30 s.
- **Si falla,** la ejecución sale en rojo y GitHub avisa por correo.
- **Lanzarlo a mano:** `gh workflow run uptime.yml`, o en local con
  `infra/scripts/uptime-check.sh`.
- **Por qué no más a menudo:** cada sondeo despierta la API unos 5 minutos. Con un sondeo cada
  hora se iría dos tercios de la concesión gratuita de Container Apps.

### Prueba de restauración de backups

`infra/scripts/restore-test.sh` (de 15 a 25 minutos, unos céntimos):
- restaura `psql-fakesnews` a hace 10 minutos en `psql-fakesnews-restoretest`;
- cuenta las filas en los dos servidores y compara las tablas, las filas y la revisión de
  alembic;
- borra siempre el servidor y el job temporales;
- termina en `RESTORE-TEST OK` o `RESTORE-TEST FAIL`.

Se corre **cada 3 meses**. Anota aquí la fecha y el resultado:

| Fecha | Resultado | Restauración |
|---|---|---|
| 2026-11-09 | OK: 9 tablas con las mismas filas, misma revisión de alembic (`d5f2b7c3e8a1`) | 9 min |
<!-- restore-test rows -->

### Consultas

En Log Analytics (`log-fakesnews`), o con
`az monitor log-analytics query -w <customerId> --analytics-query "<consulta>"`.

Llamadas a Gemini y tokens por día y paso:
```kusto
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(7d)
| extend j = parse_json(Log_s)
| where tostring(j.event) == 'llm_usage'
| summarize llamadas = count(), tokens_entrada = sum(toint(j.input_tokens)), tokens_salida = sum(toint(j.output_tokens))
    by dia = startofday(TimeGenerated), paso = tostring(j.step)
| order by dia desc
```

Búsquedas y créditos de Tavily por día (el plan gratuito da 1.000 al mes):
```kusto
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(30d)
| extend j = parse_json(Log_s)
| where tostring(j.event) == 'search_usage'
| summarize busquedas = count(), creditos = sum(toint(j.credits)) by dia = startofday(TimeGenerated)
| order by dia desc
```

Errores por evento (la misma consulta que la alerta):
```kusto
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(7d)
| where ContainerAppName_s in ('ca-fakesnews-api', 'ca-fakesnews-worker')
| extend j = parse_json(Log_s)
| where isnotempty(tostring(j.event))
| where tostring(j.level) == 'error' or tostring(j.event) == 'submissions_marked_stuck'
| summarize n = count(), ultimo = max(TimeGenerated) by event = tostring(j.event)
```

Ciclo de vida de un caso (cambia el `submission_id`):
```kusto
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(7d)
| where Log_s has '<submission_id>'
| extend j = parse_json(Log_s)
| where isnotempty(tostring(j.event))
| project TimeGenerated, app = ContainerAppName_s, evento = tostring(j.event), nivel = tostring(j.level), ruta = tostring(j.path)
| order by TimeGenerated asc
```

Arranques, escalado y sondas de cada app. Los `ProbeFailed` de la API durante un arranque en
frío son normales:
```kusto
ContainerAppSystemLogs_CL
| where TimeGenerated > ago(7d)
| where Reason_s in ('ContainerStarted', 'ContainerTerminated', 'ProbeFailed', 'KEDAScaleTargetActivated', 'KEDAScaleTargetDeactivated', 'ReplicaUnhealthy', 'BackOff')
| summarize n = count() by ContainerAppName_s, Reason_s
| order by ContainerAppName_s, n desc
```

## Si salta el aviso del presupuesto

1. Comprueba si el worker se quedó encendido:
   `az containerapp replica list -g rg-fakesnews-prod -n ca-fakesnews-worker`. Si tiene réplicas
   sin que haya envíos recientes, revisa los envíos que no están en `done` ni en `failed`
   (`psql-job.sh`) y los logs de sistema del worker.
2. Mira el desglose por recurso en Cost Management → Cost analysis, filtrando por el grupo de
   recursos.
3. Lo que más cuesta: la API (siempre encendida), el worker mientras procesa y Log Analytics si
   hay mucho volumen de logs (tiene tope diario).

## Migración desde Railway (histórico)

El corte se hizo el 2026-11-04, de 20:41 a 20:46 UTC (unos 5 min de caída). La base se volcó
por `railway ssh`, sin abrir la base de Railway a internet, y se restauró con
`infra/scripts/restore-azure.sh`. Los conteos y la revisión de alembic fueron idénticos en los
dos lados.

Railway se eliminó el 2026-11-07, por decisión del dueño y 4 días antes de lo previsto, así que
**ya no hay vuelta atrás a Railway**. Para recuperar datos están los backups de Postgres Flexible
(7 días). El volcado de la migración, `railway.dump`, debería seguir en el recurso compartido
`pgdump`, pero no se pudo comprobar el 2026-11-07 porque la cuenta de almacenamiento rechazó el acceso.
