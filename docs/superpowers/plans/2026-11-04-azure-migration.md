# Migración de Railway a Azure — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> En este repo se ejecuta **en línea** (superpowers:executing-plans), sin subagentes.

**Objetivo:** que la API, el worker, Postgres y Redis corran en Azure, con los datos de Railway migrados, y que la web de Vercel apunte a Azure.

**Arquitectura:** un grupo de recursos en `northcentralus` con:
- una VNet;
- un entorno de Container Apps (Consumption) con `api` (escala 0–2 por HTTP), `worker` (escala 0–1 con KEDA `postgresql`), `redis` (1 réplica, TCP interno) y el job `migrate`;
- Postgres Flexible B1ms con acceso privado;
- Key Vault para los secretos;
- un file share para la caché de Whisper.

Todo se describe en Bicep (`infra/`) y se despliega con GitHub Actions por OIDC con una managed identity. Las imágenes van a GHCR.

**Tech stack:** Bicep (CLI 0.48), Azure CLI, Azure Container Apps, Azure Database for PostgreSQL Flexible Server 16, Key Vault (RBAC), Azure Files, GitHub Actions, GHCR, CLI de Railway y CLI de Vercel.

**Spec:** `docs/superpowers/specs/2026-11-04-azure-migration-design.md`

## Restricciones globales

- Región `northcentralus`. Si Postgres B1ms no está disponible ahí, `canadacentral` para todo el grupo.
- Grupo de recursos `rg-fakesnews-prod`. Nombres con prefijos CAF: `vnet-`, `cae-`, `ca-`, `caj-`, `psql-`, `kv-`, `st`, `log-`, `id-`.
- Postgres: versión 16, `Standard_B1ms` (Burstable), 32 GB, sin alta disponibilidad, retención de backups de 7 días, acceso privado, base `fakesnews`.
- `api`: 0,5 vCPU / 1 GiB, min 0 / max 2. `worker`: 1 vCPU / 2 GiB, min 0 / max 1. `redis`: 0,25 vCPU / 0,5 GiB, min 1 / max 1, `redis:7-alpine` fijado por digest.
- Regla del worker: KEDA `postgresql` que cuenta los envíos con `status NOT IN ('done','failed')` y `created_at > now() - interval '20 minutes'`, con `targetQueryValue` 1 y `cooldownPeriod` 300.
- Secretos solo en Key Vault: `database-url`, `redis-url`, `redis-password`, `jwt-secret-key`, `totp-secret-encryption-key`, `anthropic-api-key`, `api-proxy-secret`, `pg-admin-password` y `keda-pg-connection`. Nunca en GitHub, en `*.bicepparam` ni en commits.
- `JWT_SECRET_KEY`, `TOTP_SECRET_ENCRYPTION_KEY` y `API_PROXY_SECRET` se copian **tal cual** de Railway.
- Las contraseñas que se generen son de 32 caracteres alfanuméricos, para que no haya que escaparlas en las URL.
- `DATABASE_URL` en Azure: `postgresql://<user>:<pass>@<fqdn>:5432/fakesnews?ssl=require`. El validador de `config.py` ya lo pasa a `+asyncpg`.
- Presupuesto de Cost Management de 10 USD al mes, con aviso al 80 % y al 100 % a `santif.arevalo@gmail.com`.
- Log Analytics: retención de 30 días y tope diario de 0,15 GB.
- Actions fijadas por SHA de commit (como en `.github/workflows/web.yml`). Permisos mínimos en cada workflow.
- Credencial federada con el sujeto exacto `repo:SantiagoTyrsArv/FAKESNEWS:ref:refs/heads/main`. La identidad tiene Contributor en el grupo de recursos y nada más (más los roles de Key Vault que se indican).
- **Producción:** cada acción sobre Railway, Vercel o la base de datos con datos reales se confirma con el dueño justo antes de hacerla. No se crean cuentas ni casos de prueba en producción.
- **Gasto de la API de Claude:** ningún envío real sin la aprobación del dueño.
- Un PR por bloque: el PR A es `infra/` + workflows (tareas 1–6) y el PR B, la documentación del corte (tarea 9). La limpieza de Railway (tarea 10) va en el PR C, 7 días después.

## Puntos a revisar

1. **Un caso colgado no debe mantener el worker encendido:** un envío no terminal con más de 20 min de antigüedad no despierta el worker. Se comprueba en la tarea 4, paso 3.
2. **El worker no se apaga a mitad de un trabajo:** con un envío en `verifying`, el worker sigue arriba pasado el `cooldownPeriod`. Tarea 4, paso 2.
3. **Los usuarios con 2FA siguen pudiendo entrar** después del corte, lo que depende de que `TOTP_SECRET_ENCRYPTION_KEY` sea idéntico. Tarea 6, paso 4, y tarea 8, paso 9.
4. **La API fría detrás del proxy de Vercel no da timeout:** la primera petición tras escalar a 0 tarda menos de 25 s. Tarea 4, paso 5.
5. **La caché de Whisper en el SMB es escribible por el usuario `app` (uid 10001).** Tarea 4, paso 4.

---

### Tarea 0: preparación de la suscripción

**Archivos:** ninguno.

**Interfaces:**
- Produce: el grupo de recursos `rg-fakesnews-prod` y la región elegida (`$LOC`), que usan todas las tareas.

- [ ] **Paso 1:** registrar los proveedores.
  `az provider register -n <ns>` para `Microsoft.DBforPostgreSQL`, `Microsoft.KeyVault`, `Microsoft.Storage`, `Microsoft.Network`, `Microsoft.ManagedIdentity` y `Microsoft.Consumption`.
  Se espera que `az provider show -n <ns> --query registrationState` devuelva `"Registered"` para cada uno.
- [ ] **Paso 2:** comprobar Postgres B1ms en la región.
  `az postgres flexible-server list-skus --location northcentralus --query "[].supportedFlexibleServerEditions[?name=='Burstable'].supportedServerVersions[].supportedVcores[?name=='Standard_B1ms'].name" -o tsv`
  Se espera `Standard_B1ms`. Si sale vacío o con restricción, repetir con `canadacentral` y usar esa región en todo el plan.
- [ ] **Paso 3:** `az group create -n rg-fakesnews-prod -l $LOC`. Se espera `provisioningState: Succeeded`.
- [ ] **Paso 4:** crear la rama: `git switch main && git pull && git switch -c feat/azure-infra`.

### Tarea 1: base de Bicep (red, logs, identidad, Key Vault, storage, presupuesto)

**Archivos:**
- Crear: `infra/main.bicep`, `infra/main.bicepparam`, `infra/bicepconfig.json`
- Crear: `infra/modules/network.bicep`, `infra/modules/monitoring.bicep`, `infra/modules/identity.bicep`, `infra/modules/keyvault.bicep`, `infra/modules/storage.bicep`, `infra/modules/budget.bicep`

**Interfaces:**
- Produce las salidas de `main.bicep`: `acaSubnetId`, `pgSubnetId`, `pgPrivateDnsZoneId`, `logWorkspaceCustomerId`, `logWorkspaceKey` (solo para el módulo del entorno, nunca como output público), `keyVaultName`, `keyVaultUri`, `appsIdentityId`, `appsIdentityClientId`, `deployIdentityClientId`, `storageAccountName` y `whisperShareName`.
- Dos identidades:
  - `id-fakesnews-apps`, que usan las Container Apps. Tiene `Key Vault Secrets User` sobre el Key Vault.
  - `id-fakesnews-deploy`, para GitHub. Tiene Contributor sobre el grupo de recursos y la credencial federada.

- [ ] **Paso 1:** `infra/bicepconfig.json` con el linter en `error` para `no-hardcoded-env-urls`, `secure-secrets-in-params` y `outputs-should-not-contain-secrets`.
- [ ] **Paso 2: `network.bicep`.**
  - VNet `10.20.0.0/16`.
  - Subred `snet-aca` `10.20.0.0/23`, delegada a `Microsoft.App/environments`.
  - Subred `snet-pg` `10.20.2.0/28`, delegada a `Microsoft.DBforPostgreSQL/flexibleServers`.
  - Zona DNS privada `privatelink.postgres.database.azure.com`, enlazada a la VNet.
- [ ] **Paso 3: `monitoring.bicep`.** `log-fakesnews`, SKU `PerGB2018`, `retentionInDays: 30` y `workspaceCapping.dailyQuotaGb: json('0.15')`.
- [ ] **Paso 4: `identity.bicep`.** Las dos identidades y la credencial federada (`issuer: https://token.actions.githubusercontent.com`, `audiences: ['api://AzureADTokenExchange']`, el sujeto de las restricciones globales), más la asignación de Contributor en el grupo de recursos.
- [ ] **Paso 5: `keyvault.bicep`.** `kv-fakesnews-<uniqueString(rg)>` (máx. 24 caracteres), `enableRbacAuthorization: true`, `enabledForTemplateDeployment: true` (lo necesita `az.getSecret` en la tarea 2), soft delete de 7 días y purge protection desactivado. Roles:
  - `Key Vault Secrets User` para `id-fakesnews-apps`;
  - `Key Vault Secrets Officer` para el usuario que despliega (parámetro `adminObjectId`, que se saca de `az ad signed-in-user show --query id -o tsv`).
- [ ] **Paso 6: `storage.bicep`.** `st<uniqueString>`, `Standard_LRS`, `allowSharedKeyAccess: true` (los montajes SMB de Container Apps lo necesitan), TLS 1.2, sin acceso público a blobs. Dos file shares, `whisper-cache` (cuota de 5 GiB) y `pgdump` (cuota de 5 GiB).
- [ ] **Paso 7: `budget.bicep`.** `Microsoft.Consumption/budgets` en el grupo de recursos: 10 USD al mes, avisos al 80 % y al 100 % (`Actual`) al correo de las restricciones globales, `startDate` el primer día del mes en curso.
- [ ] **Paso 8:** comprobar que compila y pasa el linter.
  `az bicep build --file infra/main.bicep --stdout > /dev/null` debe salir con código 0 y sin advertencias del linter.
- [ ] **Paso 9:** revisar el what-if y desplegar.
  `az deployment group what-if -g rg-fakesnews-prod -f infra/main.bicep -p infra/main.bicepparam -p adminObjectId=$ME` debe mostrar solo creaciones, sin cambios inesperados. Luego `az deployment group create …` con los mismos argumentos; se espera `Succeeded`.
- [ ] **Paso 10: commit.** `feat(infra): base network, identities, key vault, storage and budget`.

### Tarea 2: Postgres Flexible privado

**Archivos:**
- Crear: `infra/modules/postgres.bicep`
- Modificar: `infra/main.bicep`

**Interfaces:**
- Consume: `pgSubnetId`, `pgPrivateDnsZoneId` y `keyVaultName` (tarea 1).
- Produce: el output `pgFqdn`, el login de administración `fakesnews_admin` y la base `fakesnews`.

- [ ] **Paso 1:** generar la contraseña y guardarla en Key Vault **antes** del despliegue.
  `az keyvault secret set --vault-name $KV -n pg-admin-password --value <32 alfanuméricos>`.
  Se genera con `python -c "import secrets,string;a=string.ascii_letters+string.digits;print(''.join(secrets.choice(a) for _ in range(32)))"`.
- [ ] **Paso 2: `postgres.bicep`.** `psql-fakesnews`, con los valores de las restricciones globales, `network.delegatedSubnetResourceId` y `privateDnsZoneArmResourceId`. La contraseña entra como parámetro `@secure()` y en `main.bicepparam` se lee con `az.getSecret(...)`, apuntando a `pg-admin-password`. Base de datos hija `fakesnews` (UTF8).
- [ ] **Paso 3:** compilar, revisar el what-if y desplegar, como en la tarea 1, pasos 8 y 9.
  Se espera que `az postgres flexible-server show -g rg-fakesnews-prod -n psql-fakesnews --query "{s:state,v:version,sku:sku.name,net:network.publicNetworkAccess}"` devuelva `Ready`, `16`, `Standard_B1ms` y `Disabled`.
- [ ] **Paso 4:** guardar los secretos de conexión.
  - `database-url`: `postgresql://fakesnews_admin:<pass>@<pgFqdn>:5432/fakesnews?ssl=require`.
  - `keda-pg-connection`: `host=<pgFqdn> port=5432 user=fakesnews_admin password=<pass> dbname=fakesnews sslmode=require`.
- [ ] **Paso 5: commit.** `feat(infra): private postgres flexible server`.

### Tarea 3: entorno de Container Apps, Redis, API, worker y job de migraciones

**Archivos:**
- Crear: `infra/modules/containerapps-env.bicep`, `infra/modules/redis.bicep`, `infra/modules/api.bicep`, `infra/modules/worker.bicep`, `infra/modules/migrate-job.bicep`
- Modificar: `infra/main.bicep`, `infra/main.bicepparam`

**Interfaces:**
- Consume: los outputs de las tareas 1 y 2.
- Produce:
  - el parámetro `imageTag` (string, por defecto `bootstrap`);
  - la imagen `ghcr.io/santiagotyrsarv/fakesnews-api:<imageTag>`;
  - los nombres `ca-fakesnews-api`, `ca-fakesnews-worker`, `ca-fakesnews-redis` y `caj-fakesnews-migrate`;
  - el output `apiFqdn`.
  La tarea 5 usa estos nombres.
- Las variables no secretas de la app entran como el parámetro objeto `appSettings` en `main.bicepparam`. Se rellena en la tarea 6.

- [ ] **Paso 1: `containerapps-env.bicep`.** `cae-fakesnews`, workload profile solo `Consumption`, `vnetConfiguration.infrastructureSubnetId = acaSubnetId`, `internal: false` y logs a Log Analytics. Storage del entorno `whisper-cache` (Azure Files, `ReadWrite`) con la clave del storage account.
- [ ] **Paso 2: `redis.bicep`.** Ingress con `transport: 'tcp'`, `external: false`, `targetPort: 6379` y `exposedPort: 6379`. Comando `redis-server --requirepass $(REDIS_PASSWORD) --save "" --appendonly no`, con `REDIS_PASSWORD` desde `secretRef` a `redis-password` (Key Vault). Antes de desplegar se guardan en Key Vault `redis-password` (32 alfanuméricos) y `redis-url` = `redis://:<pass>@ca-fakesnews-redis:6379/0`.
- [ ] **Paso 3: secretos compartidos.** Los tres módulos de la app (`api`, `worker`, `migrate`) declaran `secrets` con `keyVaultUrl` + `identity: appsIdentityId` para `database-url`, `redis-url`, `jwt-secret-key`, `totp-secret-encryption-key`, `anthropic-api-key` y `api-proxy-secret`, y los pasan como `env` con `secretRef` a `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `TOTP_SECRET_ENCRYPTION_KEY`, `ANTHROPIC_API_KEY` y `API_PROXY_SECRET`. A eso se suman las entradas de `appSettings`. Se hace con una variable compartida en `main.bicep`, sin repetirla en cada módulo.
- [ ] **Paso 4: `api.bicep`.**
  - Ingress externo, `targetPort: 8000`, `transport: 'auto'`, `allowInsecure: false`; `PORT=8000`.
  - Escala min 0 / max 2 con una regla `http` (`concurrentRequests: '20'`).
  - Probe de liveness `/health` y probe de readiness `/health/ready`.
  - Probe de startup `/health` con `failureThreshold: 30` y `periodSeconds: 2`.
- [ ] **Paso 5: `worker.bicep`.**
  - Sin ingress. Comando `["uv","run","--frozen","arq","app.workers.arq_settings.WorkerSettings"]`.
  - Volumen `whisper-cache` montado en `/home/app/.cache` con `mountOptions: 'uid=10001,gid=10001,dir_mode=0750,file_mode=0640'`.
  - Escala min 0 / max 1 con esta regla:

  ```bicep
  rules: [{
    name: 'pending-submissions'
    custom: {
      type: 'postgresql'
      metadata: {
        targetQueryValue: '1'
        activationTargetQueryValue: '0'
        query: 'SELECT count(*) FROM submissions WHERE status NOT IN (\'done\',\'failed\') AND created_at > now() - interval \'20 minutes\''
      }
      auth: [{ secretRef: 'keda-pg-connection', triggerParameter: 'connection' }]
    }
  }]
  ```

  `cooldownPeriod: 300` y `pollingInterval: 15`.
- [ ] **Paso 6: `migrate-job.bicep`.** `triggerType: 'Manual'`, `replicaTimeout: 600`, `replicaRetryLimit: 0`, comando `["uv","run","--frozen","alembic","upgrade","head"]` y los mismos secretos y `appSettings`.
- [ ] **Paso 7: imagen inicial a mano.** Desde `apps/api`: `docker build -t ghcr.io/santiagotyrsarv/fakesnews-api:bootstrap .` y `docker push`, con un `gh auth token` que tenga el scope `write:packages`. Luego, en GitHub, hacer público el paquete `fakesnews-api` (Package settings → Change visibility). Se comprueba con `docker logout ghcr.io && docker pull ghcr.io/santiagotyrsarv/fakesnews-api:bootstrap`, que debe descargarla sin credenciales.
- [ ] **Paso 8:** guardar los secretos copiados de Railway (`jwt-secret-key`, `totp-secret-encryption-key`, `anthropic-api-key` y `api-proxy-secret`). Se leen con `railway variables --service <api> --json` y se escriben con `az keyvault secret set` **sin que se impriman en la terminal**: se canalizan en un script de un solo uso guardado en el scratchpad, que se borra al terminar.
- [ ] **Paso 9:** compilar, revisar el what-if y desplegar (tarea 1, pasos 8 y 9). Después, `az containerapp job start -n caj-fakesnews-migrate -g rg-fakesnews-prod`. La ejecución debe terminar en `Succeeded` (`az containerapp job execution list`).
- [ ] **Paso 10:** comprobar la API: `curl -fsS https://<apiFqdn>/health/ready` debe devolver `{"status":"ready"}`. Si da 503 o tarda, revisar en los logs de `ca-fakesnews-api` la conexión a Postgres o Redis.
- [ ] **Paso 11: commit.** `feat(infra): container apps for api, worker, redis and migrations`.

### Tarea 4: comprobar los riesgos del diseño

Se hace con la base de Azure todavía **sin datos reales**. Las filas de prueba se insertan en Azure y se borran en esta misma tarea.

**Archivos:**
- Crear: `infra/scripts/psql-job.sh`, que lanza un Container Apps Job puntual con `postgres:16-alpine` dentro del entorno para ejecutar `psql` contra la base privada. Recibe el SQL por argumento. Se reutiliza en las tareas 7 y 8.

**Interfaces:**
- Produce: `infra/scripts/psql-job.sh "<sql>"`, que imprime la salida de `psql` (tomada de los logs de la ejecución).

- [ ] **Paso 1:** escribir `psql-job.sh`. Crea o actualiza `caj-fakesnews-psql` con el secreto `database-url` (convertido a `postgresql://`, como lo acepta `psql`), lo arranca, espera a que termine y muestra sus logs con `az containerapp job logs show`.
  Se comprueba con `infra/scripts/psql-job.sh "select 1"`, que debe imprimir `1`.
- [ ] **Paso 2 (no se apaga a mitad de un trabajo):** insertar un usuario y un envío sintéticos con `status='verifying'` y `created_at=now()`. Se espera:
  - que en ≤ 60 s `az containerapp replica list -n ca-fakesnews-worker` muestre 1 réplica;
  - que 6 minutos después (más que el `cooldownPeriod`) siga habiendo 1.
- [ ] **Paso 3 (un caso colgado no lo mantiene encendido):** pasar el envío a `created_at = now() - interval '30 minutes'`. Se espera 0 réplicas en ≤ 6 min y que siga en 0 a los 10 min.
  **Si KEDA no llega a Postgres** (las réplicas nunca suben en el paso 2 y los logs del sistema del entorno muestran un error del escalador), aplicar el plan B de la spec: `minReplicas: 1` en `worker.bicep`, sin la regla, y anotarlo en ESTADO.md.
- [ ] **Paso 4 (la caché de Whisper es escribible):** con el worker arriba, `az containerapp exec -n ca-fakesnews-worker --command "sh -c 'touch /home/app/.cache/.probe && ls -ln /home/app/.cache'"` debe mostrar `.probe` con uid 10001. Borrar luego el archivo y las filas sintéticas (`DELETE` del envío y del usuario). Se comprueba con `select count(*) from users` = 0.
- [ ] **Paso 5 (la API fría):** esperar a que `ca-fakesnews-api` tenga 0 réplicas (unos 5 min sin tráfico) y medir `curl -o /dev/null -w '%{time_total}' https://<apiFqdn>/health/ready`. Se espera **< 25 s**. Si da más, `minReplicas: 1` en `api.bicep` y anotarlo.
- [ ] **Paso 6 (`TRUSTED_PROXY_HOPS`):** desplegar de forma temporal `mendhak/http-https-echo` (fijado por digest) como Container App en el mismo entorno con ingress externo, hacerle `curl` y mirar el `X-Forwarded-For` y la IP de origen que recibe. Si `X-Forwarded-For` termina en la IP pública del cliente y el peer es el proxy del ingress, el valor correcto es `TRUSTED_PROXY_HOPS=1`. Anotar el resultado y **borrar** la app de eco (`az containerapp delete`).
- [ ] **Paso 7: commit.** `feat(infra): psql job helper and verified scaling rules`, que incluye los ajustes de min réplicas que hayan hecho falta.

### Tarea 5: despliegue continuo con GitHub Actions

**Archivos:**
- Crear: `.github/workflows/infra.yml`, `.github/workflows/api-deploy.yml`

**Interfaces:**
- Consume: los nombres de los recursos de la tarea 3, el output `deployIdentityClientId` y las variables de repositorio (no secretos) `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` y `AZURE_SUBSCRIPTION_ID`, creadas con `gh variable set`.

- [ ] **Paso 1:** crear las tres variables con `gh variable set`. Se espera verlas en `gh variable list`.
- [ ] **Paso 2: `infra.yml`.**
  - Se dispara con `workflow_dispatch` y con push a `main` con `paths: infra/**, .github/workflows/infra.yml`.
  - Permisos `id-token: write` y `contents: read`; `concurrency: infra`.
  - Pasos: checkout, `azure/login` (OIDC, con las variables), `az deployment group create … -p imageTag=<tag actual>`. El tag actual se lee con `az containerapp show -n ca-fakesnews-api --query properties.template.containers[0].image`, para que un despliegue de infraestructura no vuelva a la imagen `bootstrap`.
- [ ] **Paso 3: `api-deploy.yml`.**
  - Se dispara con push a `main` con `paths: apps/api/**, .github/workflows/api-deploy.yml`.
  - Permisos `id-token: write`, `contents: read` y `packages: write`; `concurrency: api-deploy`, sin cancelar el despliegue en curso.
  - Pasos:
    1. build y push con `docker/build-push-action` a `ghcr.io/santiagotyrsarv/fakesnews-api:${{ github.sha }}`;
    2. `azure/login`;
    3. `az containerapp job update -n caj-fakesnews-migrate --image …:sha` y luego `az containerapp job start`, esperando con un bucle sobre `job execution show` hasta `Succeeded`; si sale `Failed`, falla el workflow;
    4. `az containerapp update` de `ca-fakesnews-api` y `ca-fakesnews-worker` con la nueva imagen.
- [ ] **Paso 4:** fijar cada `uses:` por SHA, sacado con `gh api repos/<owner>/<repo>/git/ref/tags/<vX>`, con un comentario `# vX.Y.Z`.
- [ ] **Paso 5:** validar la sintaxis con `actionlint` (`go run github.com/rhysd/actionlint/cmd/actionlint@latest` o el binario); no debe dar errores.
- [ ] **Paso 6:** abrir el PR A (tareas 1–5) con `gh pr create`. Tras la fusión, el push a `main` lanza `api-deploy.yml`. Se espera que el workflow salga en verde y que `az containerapp show -n ca-fakesnews-api --query properties.template.containers[0].image` termine en el SHA del merge.
  **Ojo:** Railway también desplegará ese merge. Es inofensivo, porque el PR no toca `apps/api`.
- [ ] **Paso 7:** probar que el sujeto OIDC es estricto: lanzar `infra.yml` por `workflow_dispatch` desde una rama distinta de `main` debe fallar en `azure/login` (`AADSTS70021`).

### Tarea 6: configuración de la app idéntica a Railway

**Archivos:**
- Modificar: `infra/main.bicepparam` (`appSettings`)

- [ ] **Paso 1:** listar las variables de los servicios de Railway (`railway variables --service <api|worker> --kv`) y clasificarlas sin imprimir los valores secretos. Se usa la lista de `apps/api/app/core/config.py` (`alias=`) para saber cuáles conoce la app.
- [ ] **Paso 2:** copiar a `appSettings` las que no son secretas con su valor de Railway (`ENVIRONMENT`, `LOG_LEVEL`, `ANTHROPIC_MODEL`, `CORS_ORIGINS`, `COOKIE_*`, límites, `VIDEO_INGEST_ENABLED`, `WHISPER_MODEL_SIZE`, etc.). `TRUSTED_PROXY_HOPS` lleva el valor que salió en la tarea 4, paso 6. No se copian las variables propias de Railway (`RAILWAY_*`, `PORT`).
- [ ] **Paso 3:** desplegar con `infra.yml` (`workflow_dispatch` tras la fusión, o en la misma rama del PR A si aún no se ha fusionado). Se espera que `az containerapp show -n ca-fakesnews-api --query "properties.template.containers[0].env[].name"` contenga todos los nombres de Railway salvo los excluidos.
- [ ] **Paso 4:** comprobar que los tres secretos copiados son idénticos sin mostrarlos: compara el SHA-256 de `railway variables` con el de `az keyvault secret show --query value` para `JWT_SECRET_KEY`, `TOTP_SECRET_ENCRYPTION_KEY` y `API_PROXY_SECRET`. Los hashes deben coincidir.
- [ ] **Paso 5: commit** en la rama del PR A, o en un PR pequeño si ya se fusionó. `feat(infra): mirror railway app settings`.

### Tarea 7: ensayo del volcado y la restauración

Se hace sin parar Railway. Solo se lee de su base.

**Archivos:**
- Crear: `infra/scripts/dump-railway.sh`: `pg_dump -Fc --no-owner --no-privileges` contra la URL pública de Railway (`railway variables --service <postgres> --kv`, `DATABASE_PUBLIC_URL`), con un `pg_dump` 16 (`docker run --rm postgres:16-alpine`). Sube el `.dump` al share `pgdump` con `az storage file upload`.
- Crear: `infra/scripts/restore-azure.sh`: job puntual `postgres:16-alpine` con el share `pgdump` montado, que ejecuta `pg_restore --clean --if-exists --no-owner --no-privileges -d <url>`.
- Crear: `infra/scripts/row-counts.sql`: un `SELECT` que devuelve `tabla|conteo` para cada tabla de `public`, ordenado por nombre, más `select version_num from alembic_version`.

- [ ] **Paso 1:** ejecutar `dump-railway.sh` y anotar cuánto tarda y cuánto pesa el volcado.
- [ ] **Paso 2:** ejecutar `restore-azure.sh` y anotar cuánto tarda. La ejecución debe terminar en `Succeeded`.
- [ ] **Paso 3:** ejecutar `row-counts.sql` en Railway (con `psql` en Docker y la URL pública) y en Azure (`psql-job.sh`), y comparar con `diff`. El resultado debe ser idéntico, incluido `version_num`.
- [ ] **Paso 4:** con los tiempos de los pasos 1–2, confirmar que el corte cabe en 30 min (dump + restore + verificación + redespliegue de Vercel). Si no cabe, avisar al dueño antes de la tarea 8.
- [ ] **Paso 5:** dejar la base de Azure con los datos del ensayo. El corte la sobrescribe con `--clean`. **No se apunta Vercel a Azure todavía.**
- [ ] **Paso 6: commit.** `feat(infra): dump, restore and row-count scripts`.

### Tarea 8: corte a producción

Cada paso marcado con ⚠ se confirma con el dueño justo antes. Se anota la hora de cada paso.

- [ ] **Paso 1:** acordar la hora con el dueño.
- [ ] **Paso 2:** comprobar que no hay trabajos en curso: en Railway, `select count(*) from submissions where status not in ('done','failed') and created_at > now() - interval '20 minutes'` debe dar 0. Si no da 0, esperar.
- [ ] **Paso 3 ⚠:** parar la API y el worker de Railway (quitar su despliegue activo o pasar a 0 réplicas desde el panel o el CLI). Postgres de Railway sigue encendido. Se comprueba con `curl https://fakesnews-production.up.railway.app/health`, que ya no debe responder 200.
- [ ] **Paso 4:** `dump-railway.sh`.
- [ ] **Paso 5 ⚠:** `restore-azure.sh`.
- [ ] **Paso 6:** `row-counts.sql` en los dos lados. El `diff` debe salir vacío. Si no sale vacío, **detenerse** y volver a arrancar Railway (vuelta atrás).
- [ ] **Paso 7:** `curl -fsS https://<apiFqdn>/health/ready` debe devolver `{"status":"ready"}`.
- [ ] **Paso 8 ⚠:** en Vercel (producción), cambiar `API_PROXY_TARGET` a `https://<apiFqdn>` y redesplegar (`vercel env` + `vercel redeploy` de la última producción, o desde el panel). El despliegue debe quedar en `Ready`.
- [ ] **Paso 9:** prueba de humo con la cuenta del dueño, que la hace él en el navegador: login (con 2FA si lo tiene), historial y `/sources`. Todo debe cargar con sus datos. ⚠ Un envío real (~0,70 USD) solo si el dueño lo aprueba; en ese caso, el worker debe arrancar y el envío llegar a `done`.
- [ ] **Paso 10:** revisar los logs de `ca-fakesnews-api` y `ca-fakesnews-worker` de los 15 minutos siguientes. No debe haber errores 5xx repetidos.
- [ ] **Paso 11:** anotar la fecha del corte. **Railway queda pausado, sin borrar, durante 7 días.**

### Tarea 9: documentación (PR B)

**Archivos:**
- Crear: `docs/AZURE.md` (runbook: recursos, cómo desplegar infraestructura y app, ver logs, lanzar migraciones a mano, `psql-job.sh`, restaurar un backup point-in-time de Postgres, rotar un secreto en Key Vault y qué hacer si salta el aviso de presupuesto)
- Modificar: `docs/ESTADO.md` (tabla «Dónde está cada cosa», registro de la sesión, resultados de la tarea 4 y pendientes)
- Modificar: los README que mencionan Railway (`README.md`, `apps/api/README.md` si existe y `apps/web/README.md`)
- Modificar: los comentarios que mencionan Railway en `apps/api/app/core/client_ip.py` (líneas del docstring) y `apps/api/Dockerfile`, solo los comentarios

- [ ] **Paso 1:** escribir y modificar los documentos de arriba.
- [ ] **Paso 2:** `uv run ruff check . && uv run ruff format --check . && uv run python -m pytest -q` en `apps/api`. Se espera todo en verde, porque solo cambian comentarios.
- [ ] **Paso 3:** `gh pr create`. La fusión, cuando el CI esté en verde, despliega en Azure por `api-deploy.yml`; se comprueba que el workflow sale en verde.

### Tarea 10: retirar Railway (PR C, 7 días después del corte)

- [ ] **Paso 1 ⚠:** con la confirmación del dueño, borrar los servicios de Railway (API, worker, Postgres y Redis) y el proyecto.
- [ ] **Paso 2:** borrar `railway.toml` y `apps/api/railway.worker.toml`, actualizar ESTADO.md y abrir un PR.
- [ ] **Paso 3:** comprobar que `git grep -i railway` solo encuentra el historial en ESTADO.md y la spec y el plan.
