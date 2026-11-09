# Estado del proyecto — FakesNews

Última actualización: **2026-11-09**. Este documento sirve para retomar el trabajo en la próxima sesión: qué hay en `main`, qué se hizo en la última sesión y qué sigue pendiente, por orden de prioridad.

## Dónde está cada cosa

| | |
|---|---|
| Web (producción) | https://fakesnews.vercel.app (Vercel, despliega `main`) |
| API (producción) | Azure Container Apps, `ca-fakesnews-api` en `rg-fakesnews-prod` (`northcentralus`). Despliega `main` con `api-deploy.yml` y la web la llama a través de `/api`. Runbook: [AZURE.md](AZURE.md) |
| Datos | PostgreSQL Flexible 18 privado (`psql-fakesnews`) y Redis interno (`ca-fakesnews-redis`). Secretos en Key Vault (`kv-fakesnews-4q4yxz5r`) |
| Calidad | SonarQube Cloud, proyecto público `SantiagoTyrsArv_FAKESNEWS` (0 issues abiertos y gate en verde en `main`, comprobado el 2026-11-06) |
| Verificación | Tavily (búsqueda, 2 créditos por afirmación, 1.000 gratis al mes) y Gemini (`gemini-3.5-flash-lite`, plan gratuito). Claves en Key Vault |
| CI/CD | `.github/workflows/web.yml` (lint, Stylelint, `tsc`, tests de `lib/` y build), `api.yml` (`ruff` y `pytest`), `osv.yml` (OSV-Scanner semanal y con cada cambio de lockfile), `api-deploy.yml` (imagen a GHCR, después las migraciones y después el rollout) e `infra.yml` (Bicep), más Dependabot (npm, uv y Actions) |
| Ramas | En remoto solo `main`. En local quedan `main` y `feat/web-improvements` (vacía). Se trabaja en una rama por cambio con PR. |

## Historial de PR fusionados

| PR | Rama | Qué trajo |
|---|---|---|
| #1 | `claude/upbeat-bardeen-j3a12a` | Proxy `/api` en Vercel para que las cookies de sesión sean del mismo origen |
| #2 | `fix/phase-1-demo-hardening` | Skills de agente de Higgsfield en el repo |
| #3 | `feat/collage-redesign` | Rediseño visual tipo collage editorial |
| #4 | `fix/dependency-vulns` | Corrección de dependencias vulnerables (OSV limpio) |
| #5 | `chore/css-tooling` | Stylelint, `pnpm css:audit` y CI de la web ([css-quality.md](css-quality.md)) |
| #6 | `fix/audit-quick-wins` | Quick wins de [AUDITORIA.md](AUDITORIA.md) |
| #7, #8 | `feat/motion`, `fix/lenis-scroll` | Animaciones (GSAP, Lenis) y arreglo del scroll |
| #9 | `feat/detective-characters` | Personajes detective en `/login` y `/register` |
| #10 | `feat/source-links` | Enlaces a la web de cada fuente en `/sources` |
| #11 | `fix/security` | Hallazgos de SonarQube y los de severidad media de seguridad: H-01 SSRF, H-02 CSP, H-03 eventos de seguridad, más H-07 |
| #12, #24, #32 | Dependabot | Lotes de actualización de dependencias |
| #31 | `fix/sonar-smells` | Resto de los avisos de SonarQube |
| #33 | `perf/mobile-lighthouse` | Lighthouse móvil a 90+ (ver abajo) |
| #34 | `fix/security-low` | H-04, H-08, H-09 y H-11 de [SEGURIDAD.md](SEGURIDAD.md) |
| #35 | `docs/audit-and-security` | AUDITORIA.md y SEGURIDAD.md versionados en `docs/`, y este registro |
| #36, #37, #38 | Dependabot | yt-dlp 2026.10.21, anthropic 2.1.0 y fastapi 0.159.1 |
| #39 | `docs/status-2026-10-25` | Registro de la sesión del 2026-10-25 |
| #40–#49 | Dependabot | API: pydantic-settings, fastapi 0.162, alembic, ruff, pytest 9.2. Web: next y eslint-config-next 16.4.3, shadcn 4.23, css-analyzer, lucide-react 1.66 |
| #50 | `feat/colombian-sources` | 9 fuentes colombianas de confianza |
| #51 | `fix/subdomain-evidence` | Las evidencias de subdominios de una fuente de confianza ya no se descartan |
| #52 | `feat/verdict-eval` | Evaluación de la calidad de los veredictos (`apps/api/evals/verdicts/`) |
| #53 | `fix/unsearchable-domains` | **No se mandan a la búsqueda los 8 medios que bloquean a Anthropic** (la verificación nunca había funcionado en producción) |
| #54 | `docs/status-2026-11-03` | Registro de la sesión del 2026-11-03 |
| #57 | `feat/azure-migration` | Infraestructura de Azure en Bicep y despliegue continuo por OIDC (sale del #55, que se cerró por mezclar infraestructura y web) |
| #58 | `fix/oidc-subject` | Sujeto OIDC con IDs inmutables y despliegues de Azure en serie |
| #59 | `fix/postgres-18` | Postgres 18 igual que en Railway, y scripts de volcado y restauración |
| #56 | `feat/web-audit` | Auditoría de la web: botones, limpieza, componentes de reportes, metadatos y GSAP diferido |
| #60, #61 | `docs/azure-runbook`, `docs/status-2026-11-04-close` | Runbook de Azure y cierre de la sesión del 2026-11-04 |
| #62 | `fix/sonar-main` | Issues de Sonar en `main` |
| #63 | `fix/osv-2026-11-06` | Avisos de OSV (`dnspython`, `minimatch`, `deepmerge`) y fallo de Dependabot `uv` |
| #75 | `docs/status-2026-11-06` | Registro del resultado del #63 |
| #76 | `ci/api-tests` | CI de la API y escaneo semanal con OSV-Scanner (cierra H-10) |
| #77 | `chore/dependency-updates-2026-11-06` | Lote de Dependabot #64–#74: `next` 16.4.5 con correcciones de seguridad, `anthropic` 2.4.0 y otros |
| #78 | `chore/remove-railway` | Se quitan `railway.toml`, `apps/api/railway.worker.toml` y `infra/scripts/dump-railway.sh` |
| #79, #80, #82 | `docs/*` | Registro de la clave rechazada y de la evaluación de veredictos con Claude |
| #81 | `docs/key-vault-rotation` | Registro del cambio de `anthropic-api-key` |
| #83, #84 | `fix/verify-json-parsing`, `fix/verify-json-strict` | Lectura del veredicto cuando el modelo lo envolvía en texto. El #88 lo sustituyó |
| #85, #86 | `docs/tavily-gemini-spec`, `docs/tavily-gemini-plan` | Diseño y plan de la migración |
| #87 | `feat/verification-failures` | `verification_failed`, topes de uso y aviso en `/submit`. Migración `c4e8a1d27b90` |
| #88 | `feat/tavily-gemini` | **La verificación pasa a Tavily y Gemini** |
| #89 | `docs/tavily-gemini-live` | Registro del cambio en producción |
| #90 | `chore/remove-anthropic` | Se retira el SDK de Anthropic y sus ajustes |
| #94 | `feat/cleaner-evidence` | Citas cortas y limpias (`snippet.py`, reglas fijas, sin modelo) y fechas en español |
| #95 | `feat/steps-hero` | La sección «Paso a paso» muestra un resultado real y tres datos en escritorio |
| #97 | `fix/processing-time-copy` | Tiempo real de proceso en la portada y `/submit` |
| #98, #99 | `ci/protect-main`, `ci/changes-fail-closed` | Comprobaciones exigibles y `api-deploy` con pruebas previas |
| #102 | `fix/auth-row-locks` | Bloqueos de fila en refresh, códigos de recuperación y fallos de inicio de sesión (B-02), y Postgres 18 en `api-check` |
| #103 | `fix/stuck-cases` | Casos colgados, cuota con concurrencia y healthcheck del worker (B-03, O-04) |
| #104 | `feat/submissions-pagination` | Paginación de `/submissions` e índices (B-04, B-05). Migración `d5f2b7c3e8a1` |
| #105 | `fix/video-download-cap` | Tope de descarga de video; se rechazan directos y videos sin duración |
| #106 | `chore/web-standalone` | Imagen Docker de la web de 1,33 GB a 386 MB |
| #107 | `test/web-client` | `apiFetch` con Vitest y MSW, y e2e del flujo principal con Playwright |
| #108 | `docs/session-2026-11-07-close` | Registro de la tarde del 2026-11-07 y especificación de `CHANGED` |
| #109 | `docs/changed-verdict-plan` | Plan del veredicto `CHANGED`, más la clave de Anthropic revocada y Railway caído |
| #110 | `feat/changed-verdict-web` | La web pinta `CHANGED` y su línea de tiempo |
| #111 | `feat/changed-verdict-api` | **La API emite `CHANGED`** |
| #112 | `docs/changed-verdict-close` | Cierre del veredicto `CHANGED` |
| #117 | `docs/verdict-eval-expansion-spec` | Diseño y plan para ampliar la evaluación de veredictos |
| #118 | `feat/verdict-eval-expansion` | Evaluación con modo ciego (`--blind`) y 20 casos |
| #119 | `docs/verdict-eval-blind-results` | Resultados de la evaluación con modo ciego (12 de 20) |
| #126 | `fix/aikido-checkout-credentials` | `persist-credentials: false` en los checkout de `api-deploy`, `infra` y `web` (Aikido) |
| #125 | `feat/alert-identity` | La alerta de logs consulta con su propia identidad de solo lectura (`id-fakesnews-alerts`) |
| #124 | `feat/observability` | Alerta de errores por correo, sondeo de disponibilidad y prueba de restauración de backups |
| #121 | `chore/pending-2026-11-09` | Diagnóstico de EFE en Tavily y detalles menores de la web, la API y la infraestructura |
| #122 | `feat/postgres-app-role` | La API y el worker se conectan con un rol de Postgres sin DDL |
| #120 | `feat/verify-claim-parts` | El modelo comprueba cada parte de la afirmación antes de dar `SUPPORTED` (ciego: 14 de 20) |

## Para retomar (2026-11-09, noche)

- **Marcar en Aikido los falsos positivos de la web** («Ignore»), si el dueño está de acuerdo. Ver «Aikido en la web» más abajo.
- **Decisión pendiente: protección de purga en Key Vault** (`CKV_AZURE_110`). Activarla impide borrar el almacén o sus secretos de forma definitiva antes de que pasen los 7 días de retención, pero **no se puede desactivar después**. Ver «IaC con Checkov» más abajo.
- **Recurso compartido `pgdump` sin uso:** el volcado de Railway ya se borró. Solo lo usa `infra/scripts/restore-azure.sh` (la restauración desde Railway). Se puede quitar de `storage.bicep`, de `containerapps-env.bicep` y de `main.bicep`, junto con ese script.

## Aikido en la web (2026-11-09, noche)

El plugin no lee el feed porque la cuenta es gratuita, así que se revisó en `app.aikido.dev/repositories/3705086` con la extensión de Chrome. Tras un escaneo nuevo quedan **9 problemas**, y ninguno exige cambiar código:

| Problema | Severidad | Veredicto |
|---|---|---|
| 2 secretos en `keyvault.bicep` | Alta | Falso positivo: son los ID públicos de los roles integrados de Azure |
| 1 secreto en `apps/api/app/core/config.py` | Media | Valores de desarrollo: la URL de Postgres de docker-compose (`fakesnews:fakesnews@postgres`) y `dev-insecure-change-me`. En producción `refuse_insecure_production_secrets` rechaza ese JWT, y la URL real viene de Key Vault |
| Inclusión de archivos en `scripts/css-audit.mjs` | Media | Falso positivo: lee una carpeta fija del build |
| Key Vault accesible públicamente | Baja | A propósito (ver «IaC con Checkov») |
| `actions/checkout` guarda credenciales | Baja | Corregido en el #126. El escaneo nuevo da 0 casos, así que Aikido lo cerrará |
| «Generic API Key» en `test_auth_flow.py`, `test_submissions.py` y otro | Baja | Contraseñas de prueba |
| Inclusión de archivos en `fbx2glb.py` | Baja | Script local de Blender de la skill `higgsfield-websites`: solo abre la ruta que se le pasa por la línea de comandos |
| 1 secreto en `tests/core/test_config.py` | Baja | Valor de prueba (`"x" * 48`) |
| «Generic API Key» en `tests/conftest.py` | Baja | Clave de prueba (`test-secret-key-at-least-32-bytes-long-for-hs256`) |

## Dependencias con Aikido (2026-11-09, noche)

El `aikido_oss_dependency_scan` sobre `apps/api/pyproject.toml`, `apps/api/uv.lock`, `apps/web/package.json` y `apps/web/pnpm-lock.yaml` da **0 hallazgos**. Para comprobar que el escáner lee bien los dos formatos, se probó con lockfiles de prueba vulnerables a propósito: `lodash` 4.17.15 en `pnpm-lock.yaml` dio 6 avisos y `jinja2` 2.10 en `uv.lock` dio 4. Aikido no marca `deepmerge`, aunque OSV y Dependabot sí. Sigue aceptado hasta el 2027-02-06.

## IaC con Checkov (2026-11-09, noche)

Checkov 3.4.3 está instalado con `uv tool install checkov`, pero el paquete no trae `checkov.exe`, solo scripts. Por eso **el plugin de Aikido sigue sin encontrarlo** en Windows. Se ejecutó directamente con `& (Join-Path (uv tool dir) 'checkov\Scripts\python.exe') -c "import sys; from checkov.main import Checkov; sys.exit(Checkov().run())" -d . --framework bicep,dockerfile,github_actions,secrets --compact`.

De 332 comprobaciones, fallan 16. Ninguna obliga a cambiar nada:

- **6 «secretos» (`CKV_SECRET_6`)** en `infra/main.bicep` y `infra/modules/redis.bicep`: son nombres de secretos de Key Vault (`jwt-secret-key`, `redis-password`…), no sus valores. Falsos positivos.
- **`CKV_DOCKER_2` (sin `HEALTHCHECK`)** en los Dockerfiles de la API y la web: Container Apps no usa `HEALTHCHECK`, sino sus propias sondas (`probes` en `infra/modules/api.bicep`).
- **`CKV_GHA_7`** en `uptime.yml`: el `base_url` del lanzamiento manual entra por `env` y no se interpola en el script, así que no hay inyección. Solo pueden lanzarlo quienes tienen permiso de escritura en el repositorio.
- **Key Vault (`CKV_AZURE_189`, `_109`)**, acceso público y sin firewall: es a propósito y está documentado en `keyvault.bicep`. El acceso es solo por RBAC, y cerrarlo exigiría un endpoint privado (unos 7 USD al mes).
- **Key Vault (`CKV_AZURE_110`, `_42`)**, sin protección de purga: el borrado temporal está activo (7 días). Activar la protección de purga es irreversible y queda como decisión pendiente (ver arriba).
- **Storage (`CKV_AZURE_35`)**, red abierta por defecto: Container Apps monta Azure Files por SMB sin VNet, así que denegar la red rompería el montaje.
- **Storage (`CKV_AZURE_43`)**: el nombre (`stfakesnews` + 8 caracteres de `uniqueString`) cumple las reglas. Checkov no resuelve la expresión, así que es un falso positivo.
- **Storage (`CKV_AZURE_206`)**, replicación LRS: basta para una caché de Whisper que se puede volver a generar.

## Revisión con Aikido (2026-11-09)

Escaneo local del plugin (SAST y secretos) sobre 229 archivos versionados: 11 hallazgos.

- **Corregidos (#126):** 3 `actions/checkout` sin `persist-credentials: false` (`api-deploy.yml`, `infra.yml` y `web.yml`). Ninguno hace `git push`. Reescaneados: limpios.
- **Falsos positivos (sin cambios):**
  - 5 «API keys» en las pruebas: son contraseñas de prueba (`test_auth_flow.py`, `test_security_events.py`, `test_reports.py`, `test_submissions.py` y `e2e/main-flow.spec.ts`);
  - 2 en `keyvault.bicep`: son los ID públicos de los roles integrados de Azure (Key Vault Secrets User y Secrets Officer);
  - 1 «path traversal» en `scripts/css-audit.mjs`: solo lee los `.css` de una carpeta fija del build, sin entrada externa.

## Observabilidad (2026-11-09)

[Especificación](superpowers/specs/2026-11-09-observability-design.md), [plan](superpowers/plans/2026-11-09-observability.md) y runbook en [AZURE.md](AZURE.md#observabilidad).

- **Alerta `alert-fakesnews-errors`:** cada hora manda un correo si la API o el worker registran un error (cuota agotada, pipeline fallido, error no controlado, fallo al encolar) o casos atascados. No salta con las trazas de Redis al apagarse. Cuesta 0,50 USD al mes.
- **Sondeo `uptime.yml`:** cada 6 horas comprueba la web y `/api/health/ready` desde GitHub Actions. No más a menudo, porque cada sondeo despierta la API.
- **Correo comprobado:** una regla temporal de prueba disparó dos veces (la segunda ya con `id-fakesnews-alerts`, #125) y el dueño confirmó que le llegaron los correos. Se borró. Hizo falta registrar el proveedor `Microsoft.Insights` en la suscripción.
- **Backups probados:** `infra/scripts/restore-test.sh` restauró a un punto en el tiempo en 9 minutos, con las 9 tablas iguales. Próxima prueba: **2027-02**.

## Azure el 2026-11-09

- **Rol de Postgres con permisos mínimos (#122):** la API y el worker se conectan como `fakesnews_app` (`database-url-app`). Puede leer y escribir filas; no puede crear ni cambiar tablas, y en `alembic_version` solo puede leer. Las migraciones, KEDA y `psql-job.sh` siguen con `fakesnews_admin`. Se probó con un job temporal antes de desplegar; después, `/api/health/ready` y `/api/sources` dan 200 y no hay errores de permisos en los logs. Detalle en [AZURE.md](AZURE.md#secretos).
- **Cuota de Gemini:** ningún `llm_quota_exhausted` en 14 días. Uso real bajo: 19 llamadas el 2026-11-07 y 7 el 2026-11-09.
- **Trazas de Redis en el worker** (`Error 111 connecting to ca-fakesnews-redis`): salen solo cuando el worker recibe SIGTERM (KEDA lo escala a 0 o un despliegue lo reemplaza), con «0 failed, 0 ongoing». Es ruido de apagado; no se pierden trabajos.
- **Borrados:** `railway.dump` del recurso compartido `pgdump` (los datos ya estaban restaurados y verificados) y el job `caj-fakesnews-restore`, que lo restauraba con `pg_restore --clean`.

## Por qué Tavily no devolvía EFE (2026-11-09)

- **EFE no bloquea a Tavily.** Con `include_domains: ["efe.com"]` devuelve artículos de EFE (1 crédito en `basic`).
- **Es el ranking:** con la lista completa, un solo medio se queda todos los resultados. Para «España es la economía de la zona euro que más crece», El País ocupó los 8; con 20 resultados, 9 eran de El País y ninguno de EFE.
- **Lo que se probó y no se fusionó:** pedir 20 resultados (cuestan lo mismo, 2 créditos en `advanced`) y quedarse con 8, con un máximo de 2 por dominio de confianza. EFE apareció en 4 casos, pero el modo ciego bajó a **11 de 20**, con 4 errores graves y 0 de 5 mixtos (`results/2026-11-09_123150_blind.md`). Con más medios distintos que confirman la parte cierta, el modelo da `SUPPORTED` a más mixtos. El parche está descartado; si se retoma, hay que medirlo junto con un cambio que proteja los mixtos, y repetir la ejecución para separar el ruido.
- **Cuota:** 44 créditos más de Tavily (40 de la evaluación y 4 de pruebas). Gasto conocido del mes: 256 de 1.000.

## Detalles cerrados el 2026-11-09

- **Sin fuentes de confianza,** `verify_claim` da un fallo técnico (`verification_failed`) y lo registra como error, en lugar de un `INSUFFICIENT` que parece un resultado.
- **`docker-compose.yml`** usa Postgres 18, como producción, con un volumen nuevo (`postgres18_data`): el de la 16 no sirve y hay que volver a sembrar los datos locales.
- **Runbook de secretos** (`AZURE.md`): el valor nuevo se sube con `--file`, no con `--value`.
- **Web:** el `import("lenis")` tiene manejo de error; GSAP espera a `document.fonts.ready` antes de cortar títulos con SplitText; las máscaras de línea dejan sitio a los descendentes (`.split-line-mask`) y el desplazamiento inicial pasa del 110 % al 125 % para que la línea siga oculta; el cursor se reclasifica al hacer scroll. Comprobado en el navegador con el build de producción.

## Comprobar cada parte de la afirmación (2026-11-09)

PR #120. El modelo separa la afirmación en partes (`parts`: datos, cifras, superlativos y alcances) y marca cada una como `confirmed`, `unconfirmed` o `contradicted`. Si da `SUPPORTED` con alguna parte sin confirmar, `_conclude` lo baja a `CHANGED` (o a `INSUFFICIENT` con una sola cita). Una diferencia de redondeo entre fuentes no cuenta.

- **Medición en ciego** (`results/2026-11-09_122316_blind.md`), frente a la base del 2026-11-08 (`_163826_blind.md`):

| | Base | #120 |
|---|---|---|
| Aciertos | 12 de 20 | **14 de 20** |
| Errores graves | 3 | 2 |
| `false` / `true` / `mixed` / `invented` | 3/6, 5/6, 1/5, 3/3 | 3/6, **6/6**, **2/5**, 3/3 |

- **Arregla** `es-mixto-1` y `co-mixto-2` (de `SUPPORTED` a `CHANGED`, eran errores graves) y `co-verdadero-1` (de `CHANGED` a `SUPPORTED`).
- **Empeora** `co-mixto-3` (de `CHANGED` a `INSUFFICIENT`) y `co-falso-1`, error grave nuevo: salió `SUPPORTED` con una sola fuente de El Tiempo, y el modelo afirmó que la captura fue «bajo el gobierno de De la Espriella», algo que el artículo no dice. La salvaguarda no lo ve porque el modelo marca esa parte como confirmada. Un `SUPPORTED` con una sola cita es el caso más frágil.
- **Sigue fallando** `co-mixto-1` (`SUPPORTED`): las fuentes confirman que la inflación bajó y el modelo marca todo como confirmado.
- Una ejecución anterior el 2026-11-08 (`_164616_blind.md`, sin la regla de redondeo) dio 11 de 20 con 2 errores 429 de Gemini.
- **Cuota:** 40 créditos de Tavily y 20 llamadas a Gemini, sin errores. Gasto conocido del mes: 212 de 1.000.

## Evaluación con modo ciego (2026-11-08)

[Especificación](superpowers/specs/2026-11-08-verdict-eval-expansion-design.md) y [plan](superpowers/plans/2026-11-08-verdict-eval-expansion.md). PR #117 y #118.

- **Qué cambió:** `--blind` quita de la búsqueda los 6 verificadores de la lista y el dominio del caso, así que nada puede copiar un chequeo publicado. Hay 12 casos nuevos (20 en total: 6 falsos, 6 verdaderos, 5 mixtos y 3 inventados), cada uno con un `coverage_url` de un medio de confianza que no es verificador. «Contaminado» cuenta ahora cualquier verificador de la lista.
- **Resultados** (`results/2026-11-08_163649.md` y `_163826_blind.md`):

| | Normal | Ciego |
|---|---|---|
| Aciertos | 14 de 20 | **12 de 20** |
| Sin contaminados | 3 de 8 | 12 de 20 |
| Errores graves | 1 | 3 |
| `false` / `true` / `mixed` / `invented` | 4/6, 6/6, 2/5, 2/3 | 3/6, 5/6, **1/5**, 3/3 |

- **Lo que dicen:**
  - La cifra fiable es la del modo ciego: **12 de 20**. Los 7 de 8 anteriores venían sobre todo de copiar chequeos.
  - **Lo débil son los mixtos (1 de 5).** El modelo da `SUPPORTED` a afirmaciones engañosas cuando las fuentes confirman la parte cierta: `es-mixto-1` («España, la economía de la zona euro que más crece») y `co-mixto-1` y `co-mixto-2` en ciego, los 3 errores graves. Solo acierta `co-mixto-3`, el dato que cambió con el tiempo.
  - Los verdaderos van bien (5 de 6 en ciego) y los inventados también (3 de 3).
  - Los falsos sin verificador (3 de 6) fallan sobre todo por la **búsqueda**, no por el modelo: `ec-falso-1` y `co-falso-1` dan `INSUFFICIENT` porque los fragmentos no hablan del tema.
  - Hay un caso discutible: en `ec-falso-2` el modelo dice que las protestas masivas fueron en octubre de 2025, no de 2026, y da `CHANGED`.
  - En modo normal, `co-inventado-1` pasó a `CONTRADICTED`: hay noticias reales de reuniones entre De la Espriella y Trump.
- **Tavily no devuelve nada de EFE:** `efe.com` está en la lista y se envía en cada búsqueda, pero no apareció en ninguna de las 40. Sí aparecen Reuters, AP y la BBC. Casi toda la cobertura de los casos nuevos está en EFE, así que en la práctica no está disponible. Falta comprobar si EFE bloquea a Tavily (cuesta créditos).
- **Cuota:** 80 créditos de Tavily y 40 llamadas a Gemini, sin errores. Gasto conocido del mes: 132 de 1.000.
- **Cómo se buscaron los casos sin Tavily:** la búsqueda web del asistente no llega a EFE, El País, Reuters, la BBC ni AP. La API de WordPress de EFE (`efe.com/wp-json/wp/v2/posts?search=…`) sí responde, y Google News también, aunque limita las peticiones.

## Para retomar (2026-11-07)

Producción funciona sobre Azure y verifica gratis con Tavily y Gemini. Lo primero en la próxima sesión:

0. **Anthropic está retirado:** el SDK salió en el #90 y el dueño borró el secreto `anthropic-api-key` el 2026-11-07 a las 05:12 UTC. Ninguna app ni job lo usa. Key Vault permite recuperarlo hasta el 2026-11-14, igual que `gemini-key` y `travily-key`, los nombres anteriores de los secretos nuevos. El dueño revocó la clave en la consola de Anthropic el 2026-11-07.
1. ~~**Protección de `main`**~~ Hecha el 2026-11-07: ver «Cómo se trabaja».
2. **Vigilar el límite diario del plan gratuito de Gemini,** que Google no publica. Si aparece `llm_quota_exhausted` en los logs, hay que ajustar los topes o pasar a un plan de pago.
3. ~~**Comprobar que Railway desapareció**~~ El dueño confirmó el 2026-11-07 que cayó.
4. **`co-mixto-1`:** sigue en `SUPPORTED` aunque ya existe `CHANGED` (#111). Le falta contexto en los fragmentos de la búsqueda, no un veredicto. Ver «Veredicto "Cambió con el tiempo"».
5. ~~**Comprobar `railway.dump`**~~ Borrado el 2026-11-09, junto con el job `caj-fakesnews-restore`.
6. **Registro detallado de la migración:** `.superpowers/sdd/2026-11-04-azure-migration/progress.md`, sin versionar. Tiene cada decisión (`Ruling:`) y las mejoras menores aplazadas:
   - ~~la app usa el usuario administrador de Postgres~~: rol `fakesnews_app` desde el #122;
   - ~~si Redis se reinicia, se pierde la cola (B-03)~~: desde el #103, el caso pasa a `failed` a los 20 minutos;
   - ~~`docker-compose.yml` sigue con Postgres 16~~: hecho el 2026-11-09;
   - ~~los scripts pasan secretos como argumento de `az` en local~~: los scripts ya usan referencias a Key Vault; el runbook de rotación pasa a `--file` (2026-11-09).

## Sesión del 2026-11-06: fallos de GitHub y OSV-Scanner

- **CI en `main`:** sin fallos. Los últimos `web`, `api-deploy`, `infra` y SonarCloud están en verde. No había PR abiertos antes del #63. El fallo de `infra` del 2026-11-04 fue en `fix/oidc-subject`, y el #58 lo resolvió.
- **Dependabot `uv` fallaba cada semana desde el 2026-10-24:** proponía `redis` 8.1.0, pero `arq` exige `redis<6`. Ahora ignora los saltos mayores de `redis`. Comprobado: la ejecución que lanzó el merge del #63 terminó bien y abrió PR de `uv`.
- **OSV-Scanner:** 3 avisos nuevos. `dnspython` y `minimatch` se corrigieron. `deepmerge` no tiene versión corregida y queda aceptado hasta el 2027-02-06. Detalle en [SEGURIDAD.md §9](SEGURIDAD.md#9-revisión-de-dependencias-y-github-del-2026-11-06).
- **SonarCloud:** los 2 issues de Bicep ya no están abiertos en `main`, así que ese pendiente queda cerrado.
- **Verificación:** API con 216 pruebas bien y 1 omitida, `ruff` limpio; web con lint, Stylelint, `tsc`, pruebas y build limpio bien.
- **Despliegue del #63:** `api-deploy` y `web` terminaron bien, y la web y `/api/health` a través de Vercel responden 200. No se pudo leer el estado de la Container App con `az`, porque la sesión pide renovar la MFA (`az login`).

## Sesión del 2026-11-07: CI de la API y lote de Dependabot

- **Azure tras el #63:** la API y el worker corren la imagen `26be11e`, con la revisión `Healthy`, 1 réplica y el 100 % del tráfico.
- **GitHub:** se activaron las alertas y las actualizaciones de seguridad de Dependabot. La única alerta abierta es la de `deepmerge`, ya aceptada.
- **CI de la API (#76):** Sonar exigió `--no-build` (regla `githubactions:S8541`). `uv run` no acepta `--no-install-project`, solo `uv sync`, por eso los pasos usan `--no-sync --no-build`.
- **Lote de Dependabot (#77):** integra los PR #64–#74. `eslint-config-next` y `@tailwindcss/postcss` subieron a la par de sus paquetes, y `lucide-react` llegó a 1.69.0, más nuevo que el 1.67.0 del PR.
- **Cuidado con `pnpm add`:** si falla por un timeout de red, las comprobaciones posteriores pasan igual con la versión anterior. Hay que mirar el diff de `package.json`.

## Veredicto «Cambió con el tiempo» (en producción desde el 2026-11-07)

[Especificación](superpowers/specs/2026-11-07-changed-verdict-design.md) y [plan](superpowers/plans/2026-11-07-changed-verdict.md). La web (#110) se desplegó antes que la API (#111).

- **El criterio de aceptación no se cumplió, y el dueño decidió fusionar igual.** En dos ejecuciones (`results/2026-11-07_140217.md` y `_142729.md`): 7 de 8, `co-mixto-2` en `CHANGED` las dos veces, ningún caso `true` o `false` en `CHANGED` y 1 error grave.
- **`co-mixto-1` es otro problema:** sus cifras son ciertas (13,1 % en 2022, 5,1 % al cierre de 2025), y Colombiacheck lo califica «Cuestionable» por falta de contexto, porque el pico venía de la pandemia. Ese contexto no aparece en los fragmentos que recibe el modelo. Una regla extra para cifras que cambiaron no movió el resultado y se quitó.
- **La evaluación cambió de escala:** un caso `mixed` solo acierta con `CHANGED`, así que los marcadores anteriores al #111 no se comparan directamente.
- **No implementado:** la regla de exigir posturas distintas en `CHANGED`. Los datos no la justificaron.

- **Decisión del dueño (2026-11-07):** `co-mixto-2`, con una parte cierta y otra falsa, se muestra igual que «cambió con el tiempo». Hay un solo veredicto nuevo, `CHANGED`.
- **Riesgo anotado en la especificación:** la etiqueta dirá «Cambió con el tiempo» sobre un dato que no cambió.
- **Despliegue:** primero el PR de la web y después el de la API, o el reporte fallaría al recibir un veredicto desconocido.

## Sesión del 2026-11-07 (noche): veredicto `CHANGED`

- **Flujo:** especificación y plan aprobados por el dueño. El plan se ejecutó sin subagentes, a petición suya, así que la revisión final la hizo el autor y es más débil que una independiente.
- **Orden de despliegue cumplido:** la portada nueva estaba en Vercel antes de fusionar la API, y `api-deploy` del #111 terminó bien, con `/api/health` en `ok`.
- **Error del autor:** un recorte de script dejó mal cerrado el JSX de `claim-card.tsx`, y el comando siguió hasta publicar la rama sin detenerse en el error. CI lo detectó en el PR y se corrigió antes de fusionar. Desde entonces, cada publicación va detrás de `set -e` y de todas las comprobaciones.
- **Prueba del plan corregida:** la de reputación pasaba antes de implementar, porque dos fuentes iguales empatan y nadie puntúa. Se cambió a pesos desiguales.
- **Aún sin observar en producción:** no se creó ningún caso de prueba, así que no se ha visto un `CHANGED` real.
- **Ramas:** el dueño borró las 12 ramas remotas de los PR #102–#113, todas fusionadas, porque el modo automático no me dejó hacerlo. En remoto solo queda `main`.
- **Alerta de Dependabot n.º 1:** es `deepmerge` (GHSA-gcqx-w48m-w2h4), baja y solo de desarrollo, sin versión corregida. Ya estaba aceptada hasta el 2027-02-06 (ver SEGURIDAD.md §9).

### Cuota gastada el 2026-11-07, tarde y noche

| Uso | Créditos de Tavily |
|---|---|
| Evaluación de la tarde | 16 |
| E2E real en local | 2 |
| Dos evaluaciones de `CHANGED` | 32 |
| Búsqueda de diagnóstico de `co-mixto-1` | 2 |
| **Total** | **52** de los 1.000 mensuales |

Gemini se usó en las mismas llamadas, dentro del plan gratuito y sin errores de cuota.

## Sesión del 2026-11-07 (tarde): evaluación, robustez y pruebas de la web

- **Evaluación:** 7 de 8, 1 error grave (`co-mixto-1` en `SUPPORTED`) y 16 créditos de Tavily. Informe en `apps/api/evals/verdicts/results/2026-11-07_115534.md`. 6 de los 8 casos están contaminados, y los 2 limpios acertaron. La muestra sigue siendo pequeña.
- **Las carreras de B-02 eran reales:** con Postgres, los dos gastos dobles y la pérdida de fallos se reproducían siempre. Las pruebas corren en `api-check` con `TEST_POSTGRES_URL`. Sin esa variable, se saltan.
- **Efecto de B-02:** dos refresh simultáneos con el mismo token cuentan como reutilización y revocan la familia. Dos pestañas que refresquen a la vez cierran la sesión.
- **Recolector en la API, no en el worker:** el worker escala a cero, así que un cron de arq no correría. Un caso sin terminar a los 20 minutos pasa a `failed` cuando el usuario crea, consulta o lista casos.
- **Sin healthcheck en Azure:** Container Apps no admite sondas exec. El de `arq --check` solo aplica a `docker-compose.yml`.
- **Video:** un video sin duración en sus metadatos ya no se analiza.
- **Tope de vitest:** quedó en 5.0.5 porque 5.1.0 tenía 5 días.
- **E2E real:** `E2E_REAL=1 pnpm test:e2e` contra API y worker locales pasó una vez, con el caso resuelto en 6,4 s. En CI la API se simula, así que el CI no detecta si la simulación deja de coincidir con la API.
- **Windows:** en local, `uv run arq` y `uv run alembic` fallan con «trampoline». Se usan `python -m alembic` y `python -c "from arq.cli import cli; cli()"`.

## Resumen de la sesión del 2026-11-06 y 2026-11-07

Para quien retome: en orden, se corrigieron los avisos de OSV y Dependabot, se creó el CI de la API, se integró el lote de Dependabot, se borró Railway y las ramas viejas, se probó Claude con una clave nueva, y se descubrió que el parser descartaba veredictos válidos. Un artículo agotó los créditos de Anthropic, y la verificación se migró a Tavily y Gemini. El detalle está en las secciones siguientes.

- **Estado de la cuenta de Anthropic:** sin créditos, según el dueño. No se usa.
- **Tavily:** 1.000 créditos al mes, con unos 50 usados en estas pruebas. La CLI `tvly` y 6 skills globales quedaron instalados en el equipo del dueño, y `~/.tavily/config.json` guarda su clave.
- **Gemini:** la primera clave era de un proyecto de prepago sin saldo. Producción usa una de un proyecto sin facturación.
- **Revisión final:** se hizo una revisión independiente de toda la rama del #88. Sus hallazgos se corrigieron antes de fusionar, salvo los riesgos aceptados de [SEGURIDAD.md §10](SEGURIDAD.md#10-cambio-de-proveedor-del-2026-11-07).
- **Limitaciones de operar desde esta sesión:** `az` pide renovar la MFA con frecuencia y por recurso. Hay que usar `az login --tenant 8d36836e-6b75-4de6-bab9-5f4b1775427f`.

## Migración a Tavily y Gemini (2026-11-07)

Los créditos de Anthropic se agotaron, y el dueño no quiere gastar más. Diseño, plan e informe de la fase 0 en `superpowers/`.

- **Resultado con el código final:** 7 de 8 aciertos con `gemini-3.5-flash-lite` y `advanced`, sin coste. Informe en `apps/api/evals/verdicts/results/2026-11-06_215527.md`.
- **Cautela:** 5 de esos casos están contaminados, así que solo 3 son limpios (2 de 3). `co-mixto-1` es inestable: salió bien en la fase 0 y mal en la evaluación final. También fallaba con Claude, y la causa de fondo es que no hay veredicto para lo que es cierto solo en parte.
- **Prompt:** se aclaró que no mencionar algo no es contradecirlo, lo que resolvió la afirmación inventada.
- **Límites de Gemini:** Google no publica los del plan gratuito. Si se agotan, las afirmaciones salen como «No se pudo verificar».
- **Comprobado en producción:** un envío real del dueño hizo 2 búsquedas y 3 llamadas a Gemini, sin errores, en 5,2 s (`f74facf7`). El reporte salió bien: las 2 afirmaciones sobre Ueno, respaldadas, con 7 y 8 fuentes, entre ellas AP, BBC y EFE. Los secretos se llaman `gemini-api-key` y `tavily-api-key`.
- **Despliegue:** `infra` falló la primera vez porque los secretos tenían otros nombres. Si cambia el mapa de secretos, hay que comprobar los nombres antes de fusionar.
- **La evaluación ya usa el modelo de producción:** avisa si el del entorno es distinto. Es el problema que escondió el fallo del parser.

## Veredictos perdidos por el parser (2026-11-07)

Dos envíos reales del dueño salieron «sin evidencia suficiente», uno de ellos con una noticia real (el cierre de Ueno Bank).

- **La clave de producción funciona.** Los logs muestran respuestas de Claude con decenas de miles de tokens.
- **Causa:** `claude-sonnet-5` escribe texto antes del JSON, y lo pone dentro de un bloque de código, aunque el prompt lo prohíbe. `_extract_final_json_text` solo leía el último bloque de texto y exigía JSON puro, así que descartaba la respuesta (`verify_claim_invalid_json`). Tras los reintentos devolvía `INSUFFICIENT`. Pasó en 4 de 5 respuestas registradas.
- **Reproducción:** una llamada igual a la de producción, de unos 0,13 USD, devolvió `SUPPORTED` con fuentes de El Tiempo, El Colombiano y Chequeado, y el parser antiguo falló.
- **Por qué la evaluación no lo vio:** usa el `ANTHROPIC_MODEL` del `.env` (`claude-sonnet-5-5`), que no produce ese formato.
- **Corrección (#83):** se unen todos los bloques de texto y se toma el último objeto JSON con `verdict`. Las evidencias se siguen validando contra los resultados reales de la búsqueda.
- **Endurecimiento (#84):** una revisión de seguridad señaló que el #83 aceptaba un `verdict` en cualquier parte del texto, y una página podía inducir al modelo a citar uno falso. Ahora solo vale el veredicto que cierra el texto, después de la última búsqueda y sin otro que lo contradiga. Si no, la respuesta se rechaza. Lo definitivo sería usar salida estructurada.
- **Gasto:** los dos envíos costaron unos 0,80 USD, porque los reintentos se cobran. Con el diagnóstico quedan unos **3,35 USD** si los créditos no cambiaron con la clave nueva.

## Artículo que agotó los créditos (2026-11-07)

Un artículo enviado a las 03:16 UTC, antes de desplegar el #83, hizo 8 llamadas de verificación con 581.520 tokens de entrada y 24 búsquedas, por unos **1,56 USD** según los logs. Cada llamada falló por el parser y se repitió, así que se pagó el doble para no obtener ningún veredicto. El dueño informa de que los créditos se agotaron; la estimación era que quedaran unos 1,80 USD, así que hay que comprobar el saldo en la consola de Anthropic.

**Riesgo abierto:** un envío grande puede costar más de 1,50 USD aunque el parser funcione. Cada llamada usa hasta 120.000 tokens de entrada por los resultados de búsqueda. Medidas pendientes de decisión: 4 afirmaciones por envío en lugar de 8, 3 búsquedas en lugar de 5, y un límite de gasto en la consola.

## Evaluación de veredictos del 2026-11-07

Informe en `apps/api/evals/verdicts/results/2026-11-06_195418.md`. Con `anthropic` 2.4.0 y `claude-sonnet-5-5`.

- **`anthropic` 2.4.0 funciona con llamadas reales:** 3 casos completos y ningún error de ejecución.
- **Resultado de los 3 primeros casos:** 2 aciertos de 3, y 1 de 2 sin contar los casos contaminados.
- **Error grave en `co-mixto-1`:** «la inflación cayó del 13% a cerca del 5%» salió `SUPPORTED`, con Colombiacheck en «Cuestionable». La explicación sí menciona que después repuntó a 6,29%, pero el veredicto no lo refleja. Se esperaba `CONTRADICTED` o `INSUFFICIENT`. La app no tiene un veredicto intermedio para lo que es cierto solo en parte.
- **`co-mixto-2`:** corrió aparte (informe `2026-11-06_201320.md`), con `CONTRADICTED`, acierto contaminado y 0,10 USD. `--max-usd` debe ser al menos 0,35, porque el script reserva esa cantidad para el primer caso.
- **Los 6 casos:** 5 aciertos de 6, pero solo 2 casos sin contaminar, con 1 acierto y el error grave de `co-mixto-1`. La muestra es pequeña.
- **Gasto:** 0,45 USD, más que los 0,35 USD estimados. El caso con 3 búsquedas costó 0,20 USD, por encima de los 0,085 USD por afirmación medidos antes. Un envío de 8 afirmaciones podría costar hasta unos **1,60 USD**, no 0,70 USD.
- **Gasto acumulado de la evaluación:** 0,72 USD, sin contar el envío real del dueño. Quedan unos 4,28 USD si los créditos no cambiaron con la clave nueva.

## Limpieza del 2026-11-07: ramas y Railway

- **Ramas:** se borraron 18 en remoto y 12 en local. Dos no estaban fusionadas como tal, pero sus parches ya estaban en `main` según `git cherry`: `feat/azure-infra` (`f4c44a1`) y `docs/azure-migration-spec` (`0714655`). Con esos SHA se pueden recuperar mientras git no los limpie.
- **Railway:** el dueño pidió borrarlo el 2026-11-07, 4 días antes de lo previsto. `railway delete` lo deja eliminado, con purga definitiva el **2026-11-09 02:25 UTC**. Hasta esa hora se puede restaurar desde el panel de Railway. Antes de borrarlo se comprobó que la API responde desde Azure y que Postgres Flexible tiene backups desde el 2026-11-04.
- **`feat/3d-experiences`:** borrada a petición del dueño (`031a376`). Solo le quedaban 2 commits propios que se anulaban entre sí, el hero 3D y su revert.
- **Clave SSH `fakesnews-railway`:** se quitó de Railway y de `~/.ssh`. `known_hosts` solo tenía `ssh.railway.com`, y el repo usa HTTPS.
- **Repo:** se quitaron `railway.toml`, `apps/api/railway.worker.toml` e `infra/scripts/dump-railway.sh`. Siguen menciones históricas a Railway en comentarios de Bicep y pruebas: son solo texto, y tocar Bicep lanzaría `infra.yml` sin necesidad.

## Sesión del 2026-11-04: migración de Railway a Azure

Motivo: el dueño tiene **Azure for Students (100 USD para un año)** y quiere aprender Azure. Diseño en `superpowers/specs/2026-11-04-azure-migration-design.md`, plan en `superpowers/plans/2026-11-04-azure-migration.md` y operación en [AZURE.md](AZURE.md).

- **Arquitectura:**
  - Container Apps en una VNet: la API con 1 réplica fija, el worker con escala 0–1 por KEDA `postgresql` y Redis con TCP interno y contraseña;
  - Postgres Flexible 18 B1ms privado;
  - Key Vault solo RBAC;
  - Azure Files para la caché de Whisper;
  - imágenes en GHCR (paquete público);
  - Log Analytics con tope diario;
  - presupuesto de 10 USD al mes con aviso.

  Coste estimado: **unos 8–13 USD al mes**.
- **Restricciones de la suscripción:** solo se puede desplegar en 5 regiones, y el tenant de la universidad no deja crear app registrations. Por eso GitHub entra con una managed identity con credencial federada. Contributor no puede asignar roles, así que las identidades, los roles y Key Vault van en `infra/bootstrap.bicep`, que se despliega a mano.
- **Comprobado antes del corte:**
  - KEDA llega al Postgres privado: el worker sube de 0 a 1 en 8 s, no se apaga a mitad de un trabajo y no se queda encendido por un caso colgado (solo cuenta envíos de los últimos 20 min).
  - `TRUSTED_PROXY_HOPS=1` es correcto detrás del ingress: se ignora un `X-Forwarded-For` falsificado.
  - La API en frío tardaba 30 s, por eso queda con 1 réplica fija.
- **Desvíos del plan:**
  - Railway usa **Postgres 18.6**, no la 16 del `docker-compose.yml`. Se recreó el servidor de Azure, que estaba vacío, en la 18.
  - El volcado se hace por `railway ssh` con una clave SSH registrada en Railway, sin abrir un proxy TCP público.
  - Los tokens OIDC de este repo usan el sujeto con IDs inmutables (`SantiagoTyrsArv@197986351/FAKESNEWS@1393968255`).
  - `infra.yml` y `api-deploy.yml` se pisaban; ahora comparten el grupo de concurrency `azure-deploy`.
- **Corte:** el 2026-11-04, de 20:41 a 20:46 UTC, **unos 5 minutos** de caída. Conteos y revisión de alembic idénticos (10/10). `API_PROXY_TARGET` de Vercel apunta a Azure en producción, preview y development. La prueba de humo del dueño (login con 2FA, historial y `/sources`) fue bien, y después del corte no hubo ningún 5xx.
- **Datos de producción en el corte:** 1 usuario (el dueño), 25 fuentes y ningún envío.
- **SonarCloud:** en Bicep se aceptaron 2 issues: Key Vault con acceso público (cerrarlo exige un private endpoint de ~7 USD al mes) y Redis sin `clientCertificateMode` (no aplica a un ingress TCP). Hay que aceptarlos también en la rama `main`, no solo en el PR.
- **Railway queda pausado hasta el 2026-11-11:** la API y el worker sin despliegue (`railway down`), y Postgres y Redis encendidos. Después se borra (tarea 10 del plan). **Ojo:** Railway sigue enlazado a GitHub, así que cada push a `main` vuelve a desplegar su API y su worker contra la base vieja. Mientras dure la pausa, hay que volver a ejecutar `railway down` después de cada merge, o desconectar el repo en Railway.

## Sesión del 2026-11-03

El dueño compró **5 USD de créditos** de la API de Claude, **en la misma clave que usa producción**, y no piensa gastar más. Quería comprobar que **los veredictos son correctos**; que la app no se rompa le importa menos. Por eso, en lugar del e2e con Playwright, se hizo una evaluación de veredictos.

- **Dependabot (#40–#49):** se combinaron en una rama temporal y se probaron en local, porque la API todavía no tiene CI (178 pruebas bien y la web completa en verde). Luego se fusionaron. El #46 y el #48 chocaban en el lockfile; se le pidió a Dependabot que los rehiciera.
- **Fuentes colombianas (#50):** antes no había ninguna. Se agregaron `colombiacheck.com` (verificador, 7/2); `lasillavacia.com`, `eltiempo.com`, `elespectador.com` y `elcolombiano.com` (medios, 6/2); y `dane.gov.co`, `registraduria.gov.co`, `banrep.gov.co` y `minsalud.gov.co` (oficiales, 8/1). Quedan fuera, a propósito, Semana, Presidencia y los ministerios políticos.
- **Subdominios (#51):** `_validated_evidence` comparaba los dominios de forma exacta, así que se descartaba la evidencia de `factual.afp.com`. Ahora una evidencia de un subdominio se guarda con el dominio de su fuente de confianza.
- **Evaluación de veredictos (#52):** diseño y plan en `superpowers/specs/2026-11-03-verdict-eval-design.md` y `superpowers/plans/2026-11-03-verdict-eval.md`, y uso en `apps/api/evals/verdicts/README.md`. Son 6 casos de Colombiacheck y La Silla Vacía (2 falsos, 2 verdaderos y 2 cuestionables), tomados de sus verificaciones publicadas. No se encontró ninguno de AFP Factual que sirviera. Tiene un freno de gasto (0,75 USD por ejecución) y nunca corre en el CI. Se lanza con `uv run python -m evals.verdicts.run --dry-run` desde `apps/api`.
- **Fallo grave encontrado (#53):** la API rechaza la petición de búsqueda **entera** (`400 not accessible to our user agent`) si `allowed_domains` incluye un sitio que bloquea el rastreador de Anthropic. Pasa con `afp.com`, `apnews.com`, `bbc.co.uk`, `bbc.com`, `efe.com`, `elpais.com`, `nytimes.com` y `reuters.com`. **En producción, todas las afirmaciones terminaban en `INSUFFICIENT`.** Ahora están en `UNSEARCHABLE_DOMAINS` (`verify.py`): siguen siendo fuentes de confianza, pero no se buscan en ellas, y quedan 17 buscables. Si aparece otro dominio bloqueado, se registra `verify_claim_domains_blocked`.
- **Primera ejecución real (2 casos):** 2 aciertos de 2, por **0,17 USD**, o sea unos 0,085 USD por afirmación. Un envío real con hasta 8 afirmaciones costaría unos **0,70 USD**. Los dos casos salieron «contaminados»: Claude citó la propia verificación de Colombiacheck. Claude usó solo fuentes colombianas. El informe está en `apps/api/evals/verdicts/results/2026-11-03_184053.md`.
- **Clave:** la clave antigua del `.env` de la raíz daba `401 invalid x-api-key`; el dueño la cambió. El script lee `.env` desde `apps/api` (que no existe), así que se lanzó exportando `ANTHROPIC_API_KEY` y `ANTHROPIC_MODEL` desde el `.env` de la raíz. Ese `.env` define `ANTHROPIC_MODEL=claude-sonnet-5-5`, mientras que el valor por defecto del código es `claude-sonnet-5`. Cuestan lo mismo (2 y 10 USD por millón de tokens de entrada y salida; búsqueda, 0,01 USD).
- **Gasto total de la sesión: 0,17 USD.** Quedan unos 4,83 USD para producción y la evaluación.
- **Pendiente del dueño:** comprobar que Railway se redesplegó con #50, #51 y #53, y que tiene la clave nueva y el modelo que corresponde.

## Sesión del 2026-10-25

- **Valoración del proyecto:** 8/10 en conjunto. Por módulo: Auth y 2FA 9,5; Fuentes 9; Seguridad 9; Documentación 9,5; Interfaz web 9; Reportes 8; Pipeline (sin la parte de Claude) 7; Submissions 7; Infraestructura y operación 5,5; Pruebas de la web 4.
- **Dependabot:** el dueño fusionó los PR #36 y #37. El #38 se probó en local (178 pruebas bien, 1 omitida, `ruff` limpio) y se fusionó. No quedan PR abiertos.
- **anthropic 2.x** ya está en `uv.lock` (2.1.0). El `pyproject.toml` sigue pidiendo `>=0.40.0`; conviene subir ese mínimo a `>=2.1`.
- Falta borrar la rama remota `dependabot/uv/apps/api/yt-dlp-2026.10.21` (PR #36, ya fusionado). El permiso automático bloqueó el borrado; se hace a mano.
- **Decisión del dueño:** hacer los puntos 1 (CI de la API) y 2 (robustez del backend) de la lista de abajo. El punto 3 (pruebas de la web) **queda en pausa hasta que el dueño lo indique**, porque todavía no hay créditos para probar.
- **Brainstorming empezado:** el dueño no ha visto ningún problema en producción (casos colgados, historial lento ni caídas del worker). Los puntos 1 y 2 son preventivos, no responden a ningún incidente. Siguiente paso: terminar el brainstorming, escribir la especificación y luego el plan. Propuesta: un PR para el CI y otro para la robustez.

## Última sesión antes de esta (2026-10-24)

### PR #33: rendimiento móvil, accesibilidad y consola

Diseño y plan: `superpowers/specs/2026-10-24-mobile-lighthouse-design.md` y `superpowers/plans/2026-10-24-mobile-lighthouse.md`.

| PageSpeed (producción) | Rendimiento | Accesibilidad | Recomendaciones | SEO |
|---|---|---|---|---|
| Móvil, antes | 87 | 96 | 96 | 100 |
| Móvil, después (3 ejecuciones) | 88 / 100 / 97 | 100 | 100 | 100 |
| Escritorio, después | 100 | 100 | 100 | 100 |

El 88 fue la primera ejecución, con la caché de imágenes de Vercel todavía fría.

- **Fuentes** con `next/font/local` (`app/fonts.ts`, `app/fonts/*.woff2`): solo el subconjunto latino, con precarga y fuentes de respaldo ajustadas. Se quitó `@fontsource-variable/*`.
- **Imágenes:** `sizes` real en móvil (`calc(100vw - 2rem)`). Se borró `hero-keyframe-960.webp`, que no se usaba.
- **Lenis** con import dinámico: en táctil y con movimiento reducido no se descarga.
- **Movimiento en táctil:** sin titulares divididos, sin parallax de los pasos y con la marquesina quieta. El escritorio no cambia.
- **Contraste:** `--insufficient` en modo claro pasa de L 0,58 a 0,52, con ≥ 4,5:1 sobre tarjeta, fondo y su tinte. La pista de la marquesina lleva `bg-ink`; el aviso era un falso positivo de axe.
- **Consola:** `me()` (`lib/auth.ts`) no llama a `/auth/me` si no existe la cookie `csrf_token`, que dura lo mismo que el refresh.

Lo que se aprendió midiendo, para no repetirlo:
- **Techo de la nota:** sin nada de JS, Lighthouse móvil daría 98. Diferir GSAP y sonner solo suma 1 punto; el resto es React y Next. Para ganar más margen habría que convertir la portada en Server Components con islas de cliente.
- **Precarga de fuentes:** quitarla (`preload: false`) empeora el FCP y el CLS.
- **Polyfills:** el aviso de «JavaScript heredado» viene del `polyfill-module` interno de Next y no se puede quitar desde la configuración.
- **Vista previa de Vercel:** está protegida, así que PageSpeed no puede medirla. Se mide en producción o con Lighthouse local (`npx lighthouse@12.6.0 … --form-factor=mobile`, mediana de 3).

### PR #34: seguridad de severidad baja

- **H-04:** el `jti` del token `mfa_pending` se registra en Redis (`SET NX`, caduca con el token) cuando el código es correcto. Un código mal tecleado no lo gasta.
- **H-08:** `disable_mfa` revoca todas las familias de refresh del usuario salvo la de la sesión actual.
- **H-09:** `validate_password_strength` rechaza las contraseñas de `app/core/data/common_passwords.txt`: las 5.791 de la lista NCSC top 100k que cumplirían las reglas. Se eligió una lista local en lugar de Have I Been Pwned.
- **H-11:** las evidencias solo aceptan URL `http(s)`. Se filtran en `_validated_evidence`, se validan en `EvidenceItem` y la web usa `evidenceUrl()` de `lib/source-url.mjs`.
- **H-06** se volvió a comprobar y está bien. **H-05** queda aceptado.

### Limpieza

- Se borraron el worktree `../FAKESNEWS-quickwins` y todas las ramas ya fusionadas, locales y remotas.
- [AUDITORIA.md](AUDITORIA.md) y [SEGURIDAD.md](SEGURIDAD.md) pasan a `docs/`, cada uno con una sección de estado al día.
- `VULNERABILIDADES.md` (raíz) sigue siendo un informe local y no se versiona.

## Pendiente, por prioridad

0. ~~**Retirar Railway**~~ Hecho el 2026-11-07, confirmado por el dueño.
1. **Calidad de los veredictos:** en ciego, **14 de 20** desde el #120 (mixtos 2 de 5). Siguientes pasos, cada uno medido con `--blind`: `co-mixto-1`, valorar exigir dos citas para `SUPPORTED` (ver `co-falso-1`) y, después, la diversidad de dominios que deja ver EFE (ver «Por qué Tavily no devolvía EFE»). Con 20 casos, dos ejecuciones del mismo código pueden diferir; antes de decidir por 1 o 2 aciertos conviene repetir.
2. ~~**Proteger `main`**~~ Hecho en el #98 y el #99.
3. ~~**Robustez del backend**~~ Hecho en #102–#106. Queda un riesgo menor en video: un audio muy comprimido podría durar mucho más que sus metadatos, y cancelar el trabajo no detiene el hilo de Whisper. Se acepta por ahora porque solo se admiten hosts que recodifican lo que se sube. La solución sería transcribir en un subproceso que se pueda matar.
4. ~~**Pruebas de la web**~~ Hecho en #107.
5. **Largo plazo:**
   - TypeScript 7 y ESLint 10;
   - ~~observabilidad (alertas, métricas, backups probados)~~: hecho en el #124; repetir `restore-test.sh` en 2027-02;
   - Server Components para la portada y `/sources`.
6. ~~**Detalles menores**~~ Hechos el 2026-11-09 (ver «Detalles cerrados el 2026-11-09»).
7. ~~**Pendiente en Azure**~~ Hecho el 2026-11-09 (ver «Azure el 2026-11-09»).
8. **Alerta de Dependabot n.º 1** (`deepmerge`, baja, solo desarrollo): está aceptada hasta el 2027-02-06 en `osv-scanner.toml`, pero sigue abierta en GitHub. Se puede descartar como «riesgo tolerable».

## Cómo se trabaja en este repositorio

- **Flujo:** especificación en `docs/superpowers/specs/`, luego plan en `docs/superpowers/plans/`, luego implementación, con la aprobación del dueño en cada paso. Un PR por cambio, con commits pequeños.
- **Fusión:** con merge commit, cuando el CI está en verde y Sonar no tiene issues nuevos.
- **Protección de `main`:** todo entra por PR, sin aprobación obligatoria porque hay un solo desarrollador. Son obligatorios `api-check`, `web-check` y SonarCloud, y la regla también aplica a los administradores. `api` y `web` corren en todos los PR y saltan su trabajo si no se toca su código; si no se puede leer la lista de archivos, corren. Si se renombra uno de esos jobs, hay que actualizar la protección o los PR quedarán bloqueados.
- **Despliegue:** `api-deploy` corre las pruebas de la API antes de construir la imagen. Una prueba en rojo detiene el despliegue.
- **Comprobaciones de la web** (`apps/web`): `pnpm lint`, `pnpm lint:css`, `pnpm exec tsc --noEmit`, `pnpm test:motion`, `pnpm test:lib`, `pnpm test:api`, `pnpm build` y `pnpm test:e2e` (después de `build`). Antes de usar APIs de Next 16, leer `node_modules/next/dist/docs/` (lo pide `apps/web/AGENTS.md`).
- **Comprobaciones de la API** (`apps/api`): `uv run python -m pytest -q`, `uv run ruff check .` y `uv run ruff format --check .`. Para las pruebas de concurrencia, `TEST_POSTGRES_URL` debe apuntar a una base desechable: se borra. En Windows, `uv run pytest` falla con «trampoline»; hay que usar `python -m pytest`.
- **Producción:** no se crean datos de prueba en producción (cuentas, casos). Los escaneos activos solo se hacen en local.
