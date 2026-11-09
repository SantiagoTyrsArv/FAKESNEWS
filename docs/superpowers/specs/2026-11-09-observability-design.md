# Observabilidad: alertas, disponibilidad y backups probados

Fecha: 2026-11-09. El dueño delegó el diseño («diseñalo tú con tu propio criterio»); todas las
decisiones de abajo son del asistente salvo donde se indica.

## Por qué

Producción (Azure Container Apps, Postgres Flexible, Redis, Vercel) solo se observa si alguien
entra a mirar los logs. Hoy existe:

- Log Analytics (`log-fakesnews`): 30 días de retención y tope de 0,15 GB al día. Se usan unos
  15 MB al día. Los logs de la API y del worker son JSON de structlog (`event`, `level`,
  `timestamp`).
- Un presupuesto mensual de 10 USD que avisa por correo al 80 % y al 100 %.
- Backups de Postgres con restauración a un punto en el tiempo (7 días), nunca probados.

Nadie se entera si la web se cae, si un envío falla, si se agota la cuota de Tavily o de Gemini o
si los casos se quedan atascados. El 2026-11-07 se agotaron créditos y se supo por casualidad.

## Objetivos

1. **Enterarse por correo, en menos de una hora, de los errores que importan:** cuota agotada,
   pipeline fallido, casos atascados, errores no controlados y fallos al encolar.
2. **Enterarse en unas horas de que el sitio no responde,** aunque nadie lo esté usando.
3. **Saber que los backups sirven:** una restauración probada, repetible con un script, y la
   fecha de la última prueba anotada.
4. **Responder rápido a las preguntas de siempre** (uso de Gemini y Tavily, errores por evento,
   casos por estado) con consultas ya escritas.

## No objetivos

- Trazas distribuidas, Application Insights u OpenTelemetry.
- Paneles o dashboards.
- Sentry u otros servicios externos de errores.
- Avisos por SMS o llamada.
- Métricas de la web en el navegador.
- Probar los backups de Redis: solo guarda la cola, y un caso perdido pasa a `failed` a los
  20 minutos (#103).

## Anti-objetivos (lo que lo haría un fracaso aunque funcione)

- **Que cueste más de unos 2 USD al mes.** La suscripción es Azure for Students, con crédito
  limitado.
- **Que avise de ruido** y el dueño aprenda a ignorar los correos. En concreto, las trazas de
  Redis al apagarse el worker (`Error 111 connecting to ca-fakesnews-redis`, en texto plano, no
  JSON) no deben disparar nada.
- **Que mantenga la API despierta.** La API escala a cero; un sondeo frecuente se comería la
  concesión gratuita de Container Apps (180.000 vCPU-s y 360.000 GiB-s al mes).
- **Que la prueba de backups deje un servidor encendido** o toque la base de producción.

## Diseño

### 1. Grupo de acciones y regla de alertas de logs (Bicep)

- **Grupo de acciones** `ag-fakesnews-email`: un receptor de correo con `budgetContactEmail`
  (ya está en `main.bicepparam`).
- **Una sola regla de búsqueda de logs** (`Microsoft.Insights/scheduledQueryRules`),
  `alert-fakesnews-errors`. Se evalúa cada hora sobre la última hora y salta con 1 resultado o
  más. Consulta, sobre `ContainerAppConsoleLogs_CL` de `ca-fakesnews-api` y
  `ca-fakesnews-worker`:
  - solo líneas que son JSON (`parse_json(Log_s)` con `event` no vacío), lo que excluye las
    trazas de texto plano del apagado;
  - `level == "error"`, más el aviso `submissions_marked_stuck`.
- **Detalle en el correo:** la consulta agrupa por `event` y cuenta, así que el correo enlaza a
  una tabla con «qué pasó y cuántas veces».
- **Sin dimensiones,** para pagar una sola serie temporal.
- **Silencio de 6 horas** después de avisar (`muteActionsDuration: PT6H`), para no recibir un
  correo por hora mientras dura un problema.
- **Coste:** 0,50 USD al mes. Es el precio más bajo de Azure Monitor para una regla de logs,
  que se aplica a frecuencias de 15 minutos o más («Alerts System Log Monitored at 15 Minute
  Frequency», API de precios de Azure, `northcentralus`, consultada el 2026-11-09).

Eventos que hoy cubre (`logger.error`/`exception`):
- de cuota: `search_quota_exhausted`, `llm_quota_exhausted` y `verification_quota_exhausted`;
- del pipeline: `run_pipeline_failed`, `run_pipeline_cancelled` y
  `run_pipeline_submission_not_found`;
- otros: `unhandled_error`, `submission_enqueue_failed`, `verify_claim_no_trusted_sources` y
  `password_hash_unreadable`;
- más el aviso `submissions_marked_stuck`.

Los avisos sueltos de verificación (`verify_claim_*_failed`) quedan fuera: un fallo aislado de
búsqueda ya se refleja en el caso y no es una avería.

### 2. Sondeo de disponibilidad (GitHub Actions)

- **Workflow nuevo** `uptime.yml`, con `schedule` cada 6 horas y `workflow_dispatch`.
- **Comprueba:**
  - `https://fakesnews.vercel.app/`, que debe dar 200;
  - `https://fakesnews.vercel.app/api/health/ready`, que debe dar 200 y `{"status":"ready"}`,
    pasando por Vercel, la API, Postgres y Redis.
- **Cada petición** tiene 90 segundos de tiempo máximo (un arranque en frío mide unos 30 s) y un
  reintento a los 60 segundos.
- **Si falla,** el workflow termina en rojo y GitHub avisa por correo de los fallos de los
  workflows programados.
- **Por qué cada 6 horas:** cada sondeo despierta la API unos 5,5 minutos (arranque más el
  enfriamiento por defecto), a 0,5 vCPU y 1 GiB.
  - Cada hora serían unos 119.000 vCPU-s al mes, dos tercios de la concesión gratuita.
  - Cada 6 horas son unos 20.000 vCPU-s y 40.000 GiB-s, alrededor del 11 %.
  - Los errores durante el uso real ya los cubre la regla de logs.
- **Coste:** cero. El repositorio es público y los minutos de Actions son gratis.
- **Lo que no detecta:** una caída de menos de 6 horas sin tráfico. Se acepta.

### 3. Prueba de restauración de backups (script)

`infra/scripts/restore-test.sh`, a mano. Hace lo siguiente:

1. Restaura `psql-fakesnews` a un punto en el tiempo de hace unos minutos, en un servidor nuevo
   `psql-fakesnews-restoretest`, en la misma subred delegada y con la misma zona DNS privada.
2. Cuenta las filas de ambos servidores con `row-counts.sql`, desde un job temporal dentro del
   entorno de Container Apps (Postgres no tiene acceso público).
3. Compara las tablas, las filas y la revisión de alembic. Las tablas con escrituras posteriores
   al punto de restauración pueden diferir; el script restaura a un instante concreto y pasa si
   el destino tiene las mismas tablas, la misma revisión de alembic y, en cada tabla, un número
   de filas menor o igual que producción y mayor que cero donde producción tiene filas.
4. **Borra siempre** el servidor temporal y el job, también si algo falla (`trap`).
5. Imprime el resultado y el tiempo que tardó la restauración.

Detalles:
- **Credenciales:** el servidor restaurado conserva el login y la contraseña del administrador.
  El job temporal recibe la conexión del servidor restaurado como secreto por valor dentro de un
  YAML temporal (`--yaml`, nunca como argumento de línea de comandos), que se borra al terminar.
- **Coste:** Burstable B1ms unos 15–20 minutos por prueba, céntimos.
- **Frecuencia:** una vez al implementar, y después cada 3 meses. Las fechas y los resultados se
  anotan en `docs/AZURE.md`.
- **Por qué no está automatizado en CI:** la identidad de despliegue tendría que poder crear y
  borrar servidores y leer la contraseña del administrador. Para una prueba trimestral, no
  compensa.

### 4. Consultas ya escritas (runbook)

Una sección «Observabilidad» en `docs/AZURE.md` con:
- qué alerta existe, qué vigila, a quién avisa y cómo silenciarla;
- el sondeo, cómo lanzarlo a mano y qué hacer si falla;
- cómo y cuándo correr `restore-test.sh`, y la tabla de pruebas hechas;
- 4 o 5 consultas KQL para copiar:
  - llamadas a Gemini por día y paso (`llm_usage`);
  - créditos de Tavily por día (`search_usage`);
  - errores por evento en los últimos 7 días;
  - el ciclo de vida de un caso por `submission_id`;
  - las réplicas y reinicios de cada app.

## Restricciones

- **Toda la infraestructura va en Bicep** (`infra/main.bicep` y módulos) y se despliega con
  `infra.yml`. Nada creado a mano en el portal.
- **La identidad de despliegue** debe poder crear las alertas y el grupo de acciones en el
  grupo de recursos. Si no puede (`bootstrap.bicep` no le dio el rol), el plan lo detecta y lo
  resuelve en `bootstrap.bicep`, que se despliega a mano.
- **Sin dependencias nuevas** en la API ni en la web.
- **Todo cambio de código o infraestructura** pasa por PR, con CI y Sonar en verde.

## Lo que queda al implementador

- La consulta KQL exacta y los nombres de las propiedades de la regla.
- La forma del correo de la regla (asunto, descripción).
- El formato de salida de `restore-test.sh` y cómo compara.
- Comprobar en real:
  - que la regla salta, provocando un evento `error` sin dañar nada, o con una regla de prueba
    temporal de umbral 0;
  - que el sondeo falla de verdad contra una URL inválida, solo en una ejecución manual de
    prueba que no se fusiona.
