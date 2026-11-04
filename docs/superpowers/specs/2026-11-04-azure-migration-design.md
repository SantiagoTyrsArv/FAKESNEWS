# Migración de la API de Railway a Azure — diseño

Fecha: 2026-11-04. Estado: borrador para aprobación del dueño.

## Por qué

El dueño tiene una suscripción **Azure for Students** con **100 USD para un año** y quiere aprovecharlos y, de paso, aprender Azure. Todo lo que hoy corre en Railway (API, worker, Postgres y Redis) pasa a Azure. **Plazo: que funcione en Azure dentro del próximo mes.**

## Objetivos

- La app funciona en Azure igual que hoy en Railway: mismas funciones y mismos datos.
- Se migran **todos los datos** de Postgres (usuarios, 2FA, casos, reputación de fuentes, reportes).
- La infraestructura queda descrita en **Bicep** dentro del repo (`infra/`) y se puede volver a crear desde cero.
- Cada push a `main` despliega solo, como hoy en Railway, mediante GitHub Actions y sin contraseñas guardadas en GitHub.
- Que cueste **unos 3–8 USD al mes**, para que los créditos alcancen el año entero, sin dejar de ser una arquitectura profesional.

## Fuera del alcance

- La web sigue en Vercel. Solo cambian sus variables de entorno.
- No se cambia el comportamiento de la app. Los únicos cambios de código permitidos son los que pida la plataforma, por ejemplo la configuración de proxies.
- Los pendientes de robustez de AUDITORIA.md (B-02, B-03, etc.) y el CI de la API (H-10) siguen siendo trabajos aparte. Si el workflow de despliegue sirve de base para el CI, mejor, pero no es un objetivo.

## Lo que sería un fracaso aunque «funcione»

- Perder o corromper datos en la migración: cuentas que no pueden entrar o casos que desaparecen.
- Que un fallo deje el worker encendido sin parar y se coma los créditos sin que nadie se entere.
- Debilitar la seguridad que ya existe: el límite de intentos por IP, el secreto del proxy, las cookies del mismo origen o las bases de datos expuestas a internet.
- Una caída de más de 30 minutos durante el corte.

## Restricciones comprobadas (2026-11-04)

- **Regiones permitidas** por la política de la suscripción: `brazilsouth`, `northcentralus`, `canadacentral`, `chilecentral` y `spaincentral`.
- **El tenant de la universidad no deja crear app registrations** (`allowedToCreateApps = false`). Para el login de GitHub Actions se usa una **user-assigned managed identity con credencial federada** de GitHub (OIDC), que el dueño de la suscripción sí puede crear.
- Proveedores ya registrados: `Microsoft.App` y `Microsoft.OperationalInsights`. Hay que registrar los que falten: `Microsoft.DBforPostgreSQL`, `Microsoft.KeyVault`, `Microsoft.Storage`, `Microsoft.Network` y `Microsoft.ManagedIdentity`.
- El repo es **público**, así que GitHub Container Registry es gratis.
- El worker no tiene tareas programadas (`cron_jobs`): solo procesa la cola (`app/workers/arq_settings.py`).
- La web llama a la API mediante `proxy.ts`, usando `API_PROXY_TARGET` y `API_PROXY_SECRET`. Para migrar basta con cambiar `API_PROXY_TARGET` en Vercel.
- El `Dockerfile` de la API ya usa `$PORT`, corre como usuario sin privilegios y arranca uvicorn con `--no-proxy-headers`. Las IP de los clientes las resuelve `app/core/client_ip.py` (`API_PROXY_SECRET` y luego `TRUSTED_PROXY_HOPS`).
- La ventana de caída aceptada para el corte es de **30 minutos como máximo**.

## Arquitectura

Región: **`northcentralus`** (decisión de Claude: está cerca de la región por defecto de las funciones de Vercel, `iad1`). Si la suscripción no deja crear Postgres Flexible ahí, se usa `canadacentral`.

Un solo grupo de recursos, por ejemplo `rg-fakesnews-prod`, con:

| Pieza | Recurso | Configuración |
|---|---|---|
| Red | VNet con una subred para el entorno de Container Apps y otra delegada a Postgres | La VNet no tiene costo. Sirve para que Postgres y Redis no estén expuestos a internet. |
| Entorno | Container Apps Environment (workload profiles, solo Consumption) integrado en la VNet | Logs a Log Analytics |
| API | Container App `api`, con ingress HTTPS externo | **min 0 / max 1–2 réplicas**, escala por HTTP. 0,5 vCPU / 1 GiB. Probes en `/health/ready` y `/health`. |
| Worker | Container App `worker`, sin ingress, comando `uv run --frozen arq app.workers.arq_settings.WorkerSettings` | **min 0 / max 1**, con una regla KEDA `postgresql` (ver abajo). 1 vCPU / 2 GiB para Whisper `small`. |
| Redis | Container App `redis` (imagen oficial `redis:7-alpine`, con la versión fijada), ingress **TCP interno** en el puerto 6379, con `requirepass` | **min 1 / max 1**, 0,25 vCPU / 0,5 GiB, sin disco. Solo guarda datos temporales: la cola de arq, los `jti` usados y los límites de peticiones. |
| Migraciones | Container Apps Job `migrate` (manual), misma imagen, comando `uv run --frozen alembic upgrade head` | Se lanza en cada despliegue, antes de actualizar la API y el worker. Hace lo mismo que el `preDeployCommand` de Railway. |
| Base de datos | Azure Database for PostgreSQL Flexible Server, **B1ms**, versión 16, 32 GB, con acceso privado (VNet) | Gratis el primer año (750 h al mes), si la suscripción lo incluye. Backups automáticos con la retención por defecto (7 días). Sin alta disponibilidad. |
| Secretos | Key Vault (RBAC) | Las Container Apps leen los secretos por referencia a Key Vault, usando su managed identity. Los secretos **no** pasan por GitHub ni por los parámetros de Bicep. |
| Caché de Whisper | Storage account Standard LRS con un file share montado en `/home/app/.cache` del worker | Así, cada vez que el worker arranca desde 0 no tiene que volver a descargar el modelo (~0,5 GB). Cuesta céntimos al mes. |
| Imágenes | GitHub Container Registry (`ghcr.io/santiagotyrsarv/fakesnews-api`), con el paquete público | API, worker y job de migraciones usan la misma imagen. La imagen no lleva secretos. |
| Logs | Log Analytics, con retención de 30 días y tope diario bajo | |
| Gasto | Presupuesto de Cost Management de **10 USD al mes**, con aviso por correo al 80 % y al 100 % | Es la defensa contra un worker que se quede encendido. |

### Escalado del worker (KEDA y Postgres)

El worker se enciende cuando hay envíos sin terminar y se apaga cuando no queda ninguno. La regla es de tipo `postgresql` y cuenta los envíos que estén en un estado no terminal (`queued`, `ingesting`, …). El builder debe sacar la lista exacta de estados del código. Detalles:

- La consulta debe cubrir también los envíos **en proceso**, no solo los encolados. Así el worker no se apaga a mitad de un trabajo, que puede durar hasta `PIPELINE_JOB_TIMEOUT_SECONDS` (900 s).
- La consulta **solo cuenta envíos recientes**: actualizados (o, si no existe esa columna, creados) en los últimos 900 s más un margen. Un caso colgado, que hoy puede ocurrir porque B-03 está pendiente, no debe mantener el worker encendido para siempre.
- Período de enfriamiento de unos 300 s antes de escalar a 0.
- La credencial de la regla sale de un secreto, por referencia a Key Vault.
- El worker, al arrancar, carga las fuentes de confianza (`load_trusted_sources`). Con escala a 0 lo hará cada vez que arranque, lo cual no es un problema.

### Red y proxies

- El ingress de Container Apps (Envoy) es **un salto** de proxy delante de la app, igual que el edge de Railway. Se espera que `TRUSTED_PROXY_HOPS=1` siga siendo correcto, pero **hay que comprobarlo**: con una petición directa, mirando qué `X-Forwarded-For` y qué IP de origen llegan. La ruta principal (Vercel con `API_PROXY_SECRET`) no depende de esto.
- Postgres y Redis solo son accesibles desde dentro de la VNet.

### Secretos y configuración

En Key Vault: `DATABASE_URL`, `REDIS_URL` (con contraseña), `JWT_SECRET_KEY`, `TOTP_SECRET_ENCRYPTION_KEY`, `ANTHROPIC_API_KEY`, `API_PROXY_SECRET` y la contraseña de administración de Postgres.

- `JWT_SECRET_KEY`, `TOTP_SECRET_ENCRYPTION_KEY` y `API_PROXY_SECRET` deben ser **exactamente los mismos que en Railway**. Si cambian, se rompen las sesiones, los secretos TOTP cifrados (nadie con 2FA podría entrar) y el proxy de Vercel.
- El resto de variables que hoy tenga Railway (`ENVIRONMENT`, `ANTHROPIC_MODEL`, `CORS_ORIGINS`, `COOKIE_*`, `TRUSTED_PROXY_HOPS`, límites, etc.) se copian como variables normales en Bicep, con los mismos valores. El dueño saca la lista completa del panel de Railway, o se lista con el CLI de Railway si está disponible.

### Despliegue continuo

Hay dos flujos, y los dos se autentican en Azure con OIDC usando la managed identity:

1. **Infraestructura** (`infra/*.bicep`): `az deployment group create`. Se lanza a mano (`workflow_dispatch`) y cuando cambia `infra/`. Es idempotente.
2. **App** (cada push a `main` que toque `apps/api/`):
   1. build de la imagen y push a GHCR con la etiqueta del SHA;
   2. el job `migrate` corre con esa imagen y se espera a que termine bien;
   3. se actualizan `api` y `worker` a esa imagen.

   Si el paso 2 falla, la API y el worker no se tocan.

Las Actions se fijan a SHA de commit, como ya se hace en el repo, para que Dependabot las mantenga.

La managed identity de despliegue recibe permisos mínimos: Contributor solo en el grupo de recursos. Su credencial federada solo vale para `repo:SantiagoTyrsArv/FAKESNEWS:ref:refs/heads/main`, más el environment de GitHub si se usa uno.

## Migración de los datos y corte

1. **Antes del corte:** con Azure ya desplegado y probado con la base vacía (health, registro y login en local contra Azure si hace falta, sin crear datos en producción), se hace un ensayo del volcado y la restauración para medir cuánto tardan.
2. **Corte** (≤ 30 min):
   1. se detienen la API y el worker en Railway; Postgres de Railway queda encendido;
   2. `pg_dump` en formato custom desde Railway, usando su URL pública;
   3. el volcado se sube al file share y un job puntual dentro de la VNet ejecuta `pg_restore` en Azure (Postgres no es accesible desde fuera);
   4. se comprueba: conteos por tabla iguales entre origen y destino, y `alembic current` en la misma revisión;
   5. se arrancan la API y el worker en Azure y se cambia `API_PROXY_TARGET` en Vercel (hace falta redesplegar para que surta efecto);
   6. prueba de humo en producción **con la cuenta existente del dueño**, sin crear datos de prueba: login (con 2FA si lo tiene), historial y `/sources`. Si el dueño lo aprueba, también un envío real (~0,70 USD).
3. **Redis no se migra:** arranca vacío. Los trabajos que estén en cola en el momento del corte se pierden. Por eso se detiene el worker de Railway solo cuando no haya envíos en curso.
4. **Vuelta atrás:** durante 7 días, Railway queda pausado pero sin borrar. Para volver, se restaura `API_PROXY_TARGET`. Lo que se haya escrito en Azure después del corte se perdería al volver; si hiciera falta, se haría el volcado en sentido contrario. Pasados los 7 días sin problemas, se borran los servicios de Railway (con la confirmación del dueño).

## Riesgos que se comprueban primero

Se comprueban antes que todo lo demás, con un despliegue mínimo, porque pueden cambiar el diseño:

1. **¿KEDA llega al Postgres privado?** El escalador lo ejecuta la plataforma; hay que confirmar que alcanza un servidor con acceso privado en la VNet. Plan B: el worker queda con **min 1** (unos +10 USD al mes, pero dentro del presupuesto del año si el resto se mantiene).
2. **Postgres B1ms gratis en la región elegida:** que la suscripción de estudiante deje crearlo en `northcentralus` y que entre en los servicios gratuitos. Si no, se usa `canadacentral`.
3. **Arranque en frío de la API detrás del proxy de Vercel:** que una petición que despierta la API desde 0 (≈5–15 s) no supere el timeout de `proxy.ts` o de Vercel. Si lo supera, la API pasa a min 1.
4. **`TRUSTED_PROXY_HOPS`:** ver arriba.

## Qué cambia en el repo

- `infra/` nueva: `main.bicep`, los módulos y un `main.bicepparam` sin secretos.
- `.github/workflows/`: los workflows de infraestructura y de despliegue de la API.
- `railway.toml` y `apps/api/railway.worker.toml` se borran **después** de borrar Railway, no antes.
- `docs/ESTADO.md` y los README que mencionan Railway se actualizan al terminar. Se añade un runbook corto: cómo desplegar, cómo ver logs, cómo correr migraciones y cómo restaurar un backup.
- Cambios de código en `apps/api`: ninguno, salvo que la comprobación de proxies lo pida. Los comentarios que mencionan Railway (`client_ip.py`, `Dockerfile`) se actualizan.

## Decisiones de Claude (el dueño puede cambiarlas)

- Región `northcentralus`, con `canadacentral` de respaldo.
- Redis como contenedor y no como Azure Cache for Redis (que costaría ~16 USD más al mes).
- VNet con Postgres y Redis privados, y la restauración con un job dentro de la VNet.
- Key Vault para los secretos.
- Un file share para la caché del modelo de Whisper.
- GHCR con el paquete público.
- Presupuesto de 10 USD al mes con aviso.
- Railway pausado 7 días como vuelta atrás antes de borrarlo.

## Lo que se deja a quien lo construya

- La estructura de los módulos Bicep y los nombres de los recursos (con el convenio de nombres de Azure, p. ej. `ca-`, `cae-`, `psql-`, `kv-`).
- Los rangos de direcciones de la VNet.
- La consulta exacta de KEDA y su umbral, dentro de las reglas de arriba.
- El tope diario de Log Analytics.
- Si las probes usan `/health` o `/health/ready`, según lo que haga cada endpoint.
