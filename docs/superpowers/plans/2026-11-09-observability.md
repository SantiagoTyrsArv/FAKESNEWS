# Observabilidad: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** recibir por correo los errores que importan y las caídas, y tener una prueba
repetible de que los backups de Postgres se pueden restaurar.

**Arquitectura:**
- una regla de búsqueda de logs y un grupo de acciones en Bicep;
- un workflow de GitHub Actions que sondea la web y la API cada 6 horas;
- un script bash que restaura Postgres a un punto en el tiempo en un servidor temporal, compara
  el número de filas y lo borra;
- un runbook en `docs/AZURE.md`.

**Tecnologías:** Bicep (`Microsoft.Insights/actionGroups` y `scheduledQueryRules`), KQL, GitHub
Actions, `az` CLI y bash.

**Especificación:** `docs/superpowers/specs/2026-11-09-observability-design.md`

## Restricciones globales

- **Coste máximo** de unos 2 USD al mes. La regla de logs cuesta 0,50 USD al mes («Alerts System
  Log Monitored at 15 Minute Frequency», API de precios de Azure, `northcentralus`, consultada el
  2026-11-09).
- **La regla no debe saltar** con las trazas de texto plano del apagado del worker.
- **El sondeo** va cada 6 horas, no más a menudo.
- **El script de restauración** borra siempre el servidor y el job temporales, y nunca escribe
  en `psql-fakesnews`.
- **Sin dependencias nuevas** en `apps/`.
- **La infraestructura** se despliega solo con `infra.yml`.

## Puntos a revisar

1. **Trazas de Redis al apagarse** (texto plano, sin `event`): la consulta debe dar 0 en las
   últimas 2 semanas, salvo los `unhandled_error` del 2026-11-04. Lo prueba la tarea 1, paso 2.
2. **Arranque en frío de la API** (unos 30 s): el sondeo no puede fallar por eso. Tiempo máximo
   de 90 s y un reintento (tarea 2).
3. **Restauración con escrituras en curso:** la comparación admite menos filas en el destino,
   pero no tablas que falten ni una revisión de alembic distinta (tarea 3).
4. **El script falla a mitad,** por ejemplo porque se acaba la sesión de `az` o falla la
   restauración: el `trap` borra igualmente el servidor y el job. Se prueba provocando un fallo
   tras crear el job (tarea 3, paso 3).
5. **La contraseña del administrador** no debe aparecer en argumentos, salida ni archivos que
   queden en disco (tarea 3).

---

### Tarea 1: Regla de alertas y grupo de acciones

**Archivos:**
- Crear: `infra/modules/alerts.bicep`
- Modificar: `infra/main.bicep` (módulo nuevo después de `monitoring`)

**Interfaces:**
- Consume: `budgetContactEmail` (parámetro existente) y el nombre del espacio de trabajo
  `log-fakesnews` (`monitoring.outputs.workspaceName`).
- Produce: el grupo de acciones `ag-fakesnews-email` y la regla `alert-fakesnews-errors`.

- [ ] **Paso 1: Escribir la consulta KQL** que irá en la regla:
  `ContainerAppConsoleLogs_CL`, con `ContainerAppName_s in ('ca-fakesnews-api','ca-fakesnews-worker')`;
  `extend j = parse_json(Log_s)` y `where isnotempty(tostring(j.event))`;
  `where tostring(j.level) == 'error' or tostring(j.event) == 'submissions_marked_stuck'`;
  `summarize n = count() by event = tostring(j.event)`.
- [ ] **Paso 2: Validarla contra producción** con `az monitor log-analytics query` sobre `ago(14d)`.
  Resultado esperado: solo `unhandled_error` (44, todos del 2026-11-04) y `run_pipeline_failed`
  (1), y ninguna fila de texto plano. Sobre `ago(2d)`: 0 filas.
- [ ] **Paso 3: Crear `alerts.bicep`.**
  - Grupo de acciones `ag-fakesnews-email` (`location: 'global'`, `groupShortName: 'fakesnews'`)
    con un receptor de correo.
  - Regla `scheduledQueryRules@2023-03-15-preview`:
    - `scopes` es el espacio de trabajo; `evaluationFrequency: 'PT1H'`, `windowSize: 'PT1H'` y
      `severity: 2`;
    - criterio `count > 0`, sin `dimensions`; `muteActionsDuration: 'PT6H'` y
      `autoMitigate: false`;
    - `displayName` «FakesNews: errores en la API o el worker» y una descripción que remite a la
      sección «Observabilidad» de `AZURE.md`.
- [ ] **Paso 4: Conectar el módulo** en `main.bicep`. `az bicep build --file infra/main.bicep`
  debe compilar sin avisos nuevos.
- [ ] **Paso 5: Commit** `feat(infra): alerta por correo de errores en la API y el worker`.
- [ ] **Paso 6: Comprobar tras desplegar:** `az monitor scheduled-query show` muestra la regla
  activa. Para probar el aviso, crear a mano una copia temporal con umbral `n >= 0` sobre
  `ago(14d)` y frecuencia `PT15M`, esperar el correo y borrarla. Anotar en el PR si llegó.

### Tarea 2: Sondeo de disponibilidad

**Archivos:**
- Crear: `.github/workflows/uptime.yml`

**Interfaces:** ninguna.

- [ ] **Paso 1: Escribir `uptime.yml`.**
  - Disparadores: `schedule: cron '17 */6 * * *'` y `workflow_dispatch` con una entrada opcional
    `base_url` (por defecto `https://fakesnews.vercel.app`).
  - Permisos: `contents: read`.
  - Un job con un paso bash que comprueba `/` (200) y `/api/health/ready` (200 y cuerpo con
    `"ready"`). Cada petición usa `curl --max-time 90` y, si falla, reintenta a los 60 s; el paso
    termina con `exit 1` si falla el reintento.
  - Acciones fijadas por SHA, como en los demás workflows (aquí no hace falta `checkout`).
- [ ] **Paso 2: Comprobar en local** la lógica del paso bash contra producción (debe salir 0) y
  contra `https://fakesnews.vercel.app/no-existe` (debe salir 1 tras reintentar).
- [ ] **Paso 3: Commit** `ci: sondeo de disponibilidad cada 6 horas`.
- [ ] **Paso 4: Comprobar tras fusionar:** lanzarlo con `workflow_dispatch` y esperar verde.

### Tarea 3: Prueba de restauración de backups

**Archivos:**
- Crear: `infra/scripts/restore-test.sh`
- Reutiliza: `infra/scripts/row-counts.sql`

**Interfaces:**
- Consume: el secreto `keda-pg-connection` (libpq, administrador), la identidad
  `id-fakesnews-apps` y el entorno `cae-fakesnews`, igual que `psql-job.sh`.

- [ ] **Paso 1: Escribir el script** (`set -euo pipefail`, en Git Bash y en Linux):
  1. Calcula `RESTORE_TIME`, la hora UTC actual menos 10 minutos.
  2. Ejecuta `az postgres flexible-server restore --source-server psql-fakesnews --name psql-fakesnews-restoretest --restore-time "$RESTORE_TIME"`.
     La red privada se hereda del servidor de origen; si `az` la exige, se pasan `--subnet` y
     `--private-dns-zone`, leídos de `psql-fakesnews`.
  3. Crea un job temporal `caj-fakesnews-restoretest` (imagen `postgres:18-alpine`, como
     `psql-job.sh`) con dos secretos por valor, `src` y `dst`. Ambos se construyen a partir de
     `keda-pg-connection`, cambiando solo el `host`. Van en un YAML creado con `mktemp` y
     `chmod 600`, que se borra justo después de `job create`.
  4. El job ejecuta `row-counts.sql` contra los dos servidores e imprime las salidas separadas
     por la marca `== src ==` / `== dst ==`. El script las lee de Log Analytics, como hace
     `psql-job.sh`.
  5. Compara: mismas tablas, misma línea `alembic_version=`, y en cada tabla `dst <= src` y
     `dst > 0` si `src > 0`. Imprime `RESTORE-TEST OK` o `RESTORE-TEST FAIL` con la tabla que
     falla, y los minutos que tardó la restauración.
  6. `trap cleanup EXIT` borra el job, el servidor `psql-fakesnews-restoretest` (`--yes`) y el
     YAML temporal, sea cual sea el resultado.
- [ ] **Paso 2: Revisar** que ninguna línea pasa la contraseña como argumento (`grep -n "password\|PGPASS" infra/scripts/restore-test.sh`):
  solo puede aparecer dentro del YAML temporal.
- [ ] **Paso 3: Comprobar el `trap`:** ejecutar con `RESTORE_TEST_FAIL_AFTER_JOB=1`, que hace
  `exit 1` justo después de crear el job. Al terminar, ni el servidor ni el job deben existir
  (`az postgres flexible-server list` y `az containerapp job list`).
- [ ] **Paso 4: Ejecutarlo de verdad.** Resultado esperado: `RESTORE-TEST OK`; después, ningún
  recurso `*restoretest*`.
- [ ] **Paso 5: Commit** `feat(infra): script de prueba de restauración de backups`.

### Tarea 4: Runbook y estado

**Archivos:**
- Modificar: `docs/AZURE.md` (sección nueva «Observabilidad») y `docs/ESTADO.md`.

- [ ] **Paso 1: Sección «Observabilidad» en `AZURE.md`.**
  - La alerta: qué vigila, cómo se ve el correo y cómo desactivarla
    (`az monitor scheduled-query update --disabled true`).
  - El sondeo: cada cuánto corre y cómo lanzarlo.
  - `restore-test.sh`: cada 3 meses, con la tabla de pruebas hechas (la fecha y el resultado de
    la tarea 3).
  - Cinco consultas KQL, cada una probada con `az monitor log-analytics query` antes de pegarla:
    llamadas a Gemini por día y paso, créditos de Tavily por día, errores por evento en 7 días,
    el ciclo de vida de un caso por `submission_id`, y las réplicas y reinicios de cada app
    (`ContainerAppSystemLogs_CL`).
- [ ] **Paso 2: Actualizar `ESTADO.md`:** historial de PR, una sección del 2026-11-09 y, en
  «Pendiente», marcar la observabilidad como hecha y anotar la próxima prueba de restauración
  (2027-02).
- [ ] **Paso 3: Commit** `docs: runbook de observabilidad`.
