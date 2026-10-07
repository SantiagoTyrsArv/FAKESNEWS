# Auditoría FakesNews — código + producción

- **Fecha:** 2026-10-07 · **Commit auditado:** `21404ea` (rama `main`, el mismo desplegado en Railway)
- **Alcance en vivo:** `https://fakesnews.vercel.app` (web) y `https://fakesnews-production.up.railway.app` (API). Railway proyecto `luminous-harmony` (servicios `FAKESNEWS`, `upbeat-wholeness` = worker, `Postgres`, `Redis-1mfD`), Vercel proyecto `fakesnews`.
- **Modo:** solo lectura sobre el código. Pruebas en producción no destructivas con **una cuenta de prueba nueva** (`audit-634ff5fd@example.com`, creada para esta auditoría). **Sin casos de LLM**: no había créditos, así que el pipeline se evaluó solo por código y tests.

---

## 1. Resumen ejecutivo

**Nota general: 6.0 / 10.** La ponderación da 6.52; el tope por criterio de aceptación incumplido la baja a 6.0.

- **Fortalezas:**
  1. Autenticación muy bien construida. Comprobado en producción: rotación de refresh con revocación de familia, CSRF de doble envío, lockout, cookies `HttpOnly; Secure; SameSite=Lax`, y TOTP con protección contra reutilización.
  2. Anti-alucinación determinista: una cita solo pasa si su URL salió de la búsqueda real y su dominio está en la lista blanca; sin citas válidas el veredicto se fuerza a INSUFFICIENT.
  3. Configuración de producción endurecida: `/docs` cerrado, CORS sin reflejo, cabeceras de seguridad en la API, fail-fast con secretos débiles, Postgres y Redis solo en la red privada, ningún secreto en el repo ni en el bundle.
- **Riesgos:**
  1. Con la 2FA opcional, **una cuenta nueva obtiene sesión completa solo con la contraseña** (criterio 2 incumplido).
  2. **No hay ningún control de costo del LLM**: el registro es abierto y los envíos no tienen límite por usuario, rate limit ni tope de gasto.
  3. El pipeline no es viable en producción tal como está: sin créditos de LLM, transcripción de video al límite de memoria (1 GB), timeout de arq de 300 s que deja casos colgados, y SSRF por redirecciones sin cubrir.
- **Veredicto:**
  - **Demo:** no está lista en producción. No hay usuario demo ni casos sembrados (el seed se niega a correr en producción) y un caso real termina en `failed` sin créditos. Sirve para demostrar la autenticación y las fuentes.
  - **Piloto con usuarios reales:** no todavía. Faltan cuotas y topes de gasto, 2FA obligatoria (o cambiar el criterio), un reaper de casos colgados y backups.
  - **Producción seria:** además de lo anterior, CI con tests, staging separado, observabilidad y alertas, contenedores sin root y SSRF completo.

## 2. Tabla de puntajes

| Área | Nota | Peso | Justificación |
|---|---:|---:|---|
| A. Autenticación y 2FA | 7.0 | 25% | Implementación sólida y verificada en vivo; la 2FA opcional permite sesión completa solo con contraseña, y hay enumeración vía registro y 423. |
| B. Pipeline de IA | 5.0 | 25% | Buenas defensas anti-alucinación y anti-inyección; sin control de costos, con SSRF parcial, timeouts que dejan casos colgados y video inviable con 1 GB. |
| C. Reputación de fuentes | 8.0 | 15% | Matemática, condiciones y deduplicación correctas, documentación honesta y tests al 98%; actualización sin bloqueo de fila y reprocesos que duplican. |
| D. Reportes y principio de producto | 7.0 | 10% | Lenguaje no absoluto y reporte trazable; el veredicto no se reconcilia con la postura de la evidencia y el snippet no se valida. |
| E. Frontend y UX | 7.0 | 10% | TypeScript estricto, lint y build limpios, sin XSS; falta `/sources/[domain]` (404 en vivo) y la web no envía cabeceras de seguridad. |
| F. Arquitectura y código | 7.0 | 8% | Código limpio, logging estructurado y configuración tipada; hay imports cruzados de modelos entre módulos y el modelo Whisper se recarga en cada trabajo. |
| G. Infra y DevOps | 4.5 | 4% | Red privada y secretos en la plataforma; sin CI, sin staging, contenedores como root, healthcheck no aplicado y sin backups, alertas ni límites de gasto. |
| H. Tests, docs y demo | 6.0 | 3% | 123 tests pasan y el README es muy completo; demo no sembrada en producción, sin plan B y ruff format falla. |

**Cálculo ponderado:**
7.0·0.25 + 5.0·0.25 + 8.0·0.15 + 7.0·0.10 + 7.0·0.10 + 7.0·0.08 + 4.5·0.04 + 6.0·0.03
= 1.75 + 1.25 + 1.20 + 0.70 + 0.70 + 0.56 + 0.18 + 0.18 = **6.52**

**Topes aplicados:**
- Criterio de aceptación 2 **fallido**, así que la nota general queda limitada a 6 → **6.0**.
- Ningún área tiene una vulnerabilidad crítica confirmada, así que no se aplica el tope de 4 por área. El hallazgo de costos (H-02) se clasificó como Alta, no Crítica, porque requiere una cuenta registrada y el gasto lo limita la cuenta del proveedor. Si no hay tope de gasto en Anthropic, debería tratarse como Crítico y B bajaría a 4.

**Subcriterios por área (promedio redondeado hacia abajo):**
- **A:** hashing 8 · flujo dos pasos 3 · TOTP 9 · recuperación 8 · sesiones 8 · rate limit 7 · pruebas 8 · frontend auth 7 → 7.25 → 7.0
- **B:** ingesta 5 · extracción 8 · verificación 6 · inyección 7 · costos 2 · viabilidad 4 · pruebas 8 → 5.7 → 5.0. Bajé medio punto más porque nada se pudo verificar en vivo y el pipeline hoy no puede completar un caso en producción.
- **C:** matemática 9 · condiciones 9 · idempotencia 6 · transparencia 7 · docs 9 · pruebas 9 → 8.2 → 8.0
- **D:** lenguaje 8 · trazabilidad 8 · regla de evidencia 6 → 7.3 → 7.0
- **E:** páginas 6 · calidad 8 · seguridad 6 · rendimiento 8 → 7.0
- **F:** modularidad 6 · datos 7 · mantenibilidad 8 · rendimiento 7 → 7.0
- **G:** despliegue 5 · secretos 8 · dependencias 6 · observabilidad 3 · CI/entornos 2 → 4.8 → 4.5
- **H:** pruebas 7 · documentación 8 · demo 3 → 6.0

## 3. Resultados de ejecución (locales)

| Herramienta | Resultado | Detalle |
|---|---|---|
| `pytest --cov` (apps/api) | **123 passed, 1 skipped** (31 s) | Cobertura total reportada: **83%**. |
| Cobertura por módulo | Ver notas | `auth/routers.py` 60%, `auth/service.py` 64%, `sources/reputation.py` 98%, `pipeline/verify.py` 93%, `url_safety.py` 100%, `workers/arq_settings.py` 0%, `pipeline/transcribe.py` 50%. |
| Tests de integración | **No ejecutados** | Requieren `RUN_INTEGRATION_TESTS=1` y Docker. Docker Desktop no estaba corriendo (`failed to connect to the docker API`). |
| `ruff check` | ✅ All checks passed | |
| `ruff format --check` | ❌ 1 archivo | `tests/sources/test_reputation.py:172`. |
| `pip-audit` (lock exportado, sin dev) | ✅ No known vulnerabilities | |
| `pnpm lint` (eslint) | ✅ 0 errores | |
| `tsc --noEmit` | ✅ 0 errores | `strict: true` en `apps/web/tsconfig.json:7`. |
| `next build` | ✅ | 11 rutas; `.next/static/chunks` = 880 KB sin comprimir (mayor chunk 224 KB). |
| `pnpm audit --prod` | ❌ 3 high | `braces` y `@modelcontextprotocol/sdk` (vía `shadcn`, que está en `dependencies`), y `source-map-js` (vía `next>postcss`). Todo es tooling de build, no runtime del navegador. |
| Secretos (gitleaks) | **No ejecutado** | Necesita Docker. |
| Secretos (manual, 20 commits, `git log --all -p`) | ✅ Sin secretos reales | Solo valores de desarrollo intencionalmente públicos (ver sección 7, H-14). `.env` nunca se versionó. |

**Sobre la cobertura de auth:** la cifra está subestimada. Los 30 tests de auth sí recorren el login (`tests/auth/test_auth_flow.py:98`, `:115`, `:202`…), pero coverage no sigue el código que corre dentro de greenlets de SQLAlchemy async, y no hay `concurrency = ["greenlet"]` en `pyproject.toml`. [PROBABLE]

## 4. Verificaciones en producción

| # | Prueba | Esperado | Real | Estado |
|---|---|---|---|---|
| P1 | HTTP→HTTPS | Redirección | Web `308`, API `301` a https | ✅ |
| P2 | Certificados | Válidos | Web `*.vercel.app` (GTS, vence 2026-11-27); API `*.up.railway.app` (Let's Encrypt, vence 2026-12-26) | ✅ |
| P3 | HSTS | Presente | Web `max-age=63072000; includeSubDomains; preload`; API `max-age=31536000; includeSubDomains` | ✅ |
| P4 | Cabeceras de la API (`GET /health`) | CSP, nosniff, XFO, Referrer, Permissions | `default-src 'none'; frame-ancestors 'none'`, `nosniff`, `DENY`, `no-referrer`, `camera=(), microphone=(), geolocation=()`, COOP/CORP | ✅ |
| P5 | Cabeceras de la web (`GET /`) | CSP y XFO o frame-ancestors | **Ausentes**: no hay CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy ni Permissions-Policy. `Access-Control-Allow-Origin: *` en el HTML estático (default de Vercel). | ❌ (H-09) |
| P6 | Fuga de tecnología | Mínima | `Server: Vercel` y `Server: railway-hikari`, sin versiones; `x-powered-by` ausente | ✅ |
| P7 | CORS preflight con `Origin: https://evil.example` | No reflejar | `400`, sin `access-control-allow-origin` | ✅ |
| P8 | CORS simple evil y `Origin: null` | No reflejar | Sin `allow-origin` | ✅ |
| P9 | CORS con el origen legítimo | Permitir | `allow-origin: https://fakesnews.vercel.app`, con credenciales | ✅ |
| P10 | `/docs`, `/redoc`, `/openapi.json`, `/metrics`, `/.env`, `/.git/HEAD`, `/admin`, `/debug` (API y web) | 404 | Todos `404` | ✅ |
| P11 | Source maps `*.js.map` (15 chunks) | No servidos | `403` | ✅ |
| P12 | Secretos en el bundle (740 KB, 15 chunks) | Ninguno | Sin `sk-ant`, JWT, `API_PROXY_SECRET` ni `railway.internal`. Único base URL: `"/api"` | ✅ |
| P13 | JSON inválido y campos faltantes | Sin trazas | `422` con detalle de Pydantic, sin stack. **Eco del `input`**: con un password de más de 256 caracteres la respuesta lo devuelve. | ⚠️ (H-17) |
| P14 | UUID inválido o inexistente sin sesión | 401 | `401 "sesión inválida o expirada"` | ✅ |
| P15 | JWT `alg=none` forjado | 401 | `401` | ✅ |
| P16 | Registro duplicado | Mensaje genérico | `409 "Ese correo ya está registrado."` | ❌ (H-06) |
| P17 | Login sin 2FA activada | Sin sesión completa (criterio 2) | `200 {"status":"authenticated"}` + cookies; `GET /auth/me` y `GET /submissions` → `200` | ❌ (H-01) |
| P18 | Atributos de las cookies | HttpOnly, Secure, SameSite | `access_token`: HttpOnly; Max-Age=900; Path=/; SameSite=lax; Secure. `refresh_token`: HttpOnly; Max-Age=2592000; Path=/api/auth; SameSite=lax; Secure. `csrf_token`: no HttpOnly (diseño double-submit); Path=/; Secure | ✅ |
| P19 | Tokens en la URL | Ninguno | Ninguno | ✅ |
| P19b | Tokens en sessionStorage | Ninguno | El token `mfa_pending` (5 min) se guarda en `sessionStorage` | ⚠️ (H-15) |
| P20 | `POST /submissions` sin CSRF o con CSRF falso | 403 | `403 "Token CSRF inválido o ausente."` (no se crea nada) | ✅ |
| P21 | Token `mfa_pending` como bearer, como cookie, o en `/2fa/setup` | 401 | `401` en los tres casos | ✅ |
| P22 | TOTP inválido / reutilizado | 401 | `401` / `401` | ✅ |
| P23 | Token `mfa_pending` reutilizado tras un login exitoso | Rechazo | **`200`**: emite una segunda sesión (con código de recuperación) | ⚠️ (H-12) |
| P24 | Rotación del refresh / refresh viejo / refresh nuevo tras el reuso | 200 / 401 / 401 | `200` / `401 "se detectó reutilización"` / `401` (familia revocada) | ✅ |
| P25 | `/auth/refresh` con CSRF incorrecto | 403 | `403` | ✅ |
| P26 | Código de recuperación: primer uso / segundo uso | 200 / 401 | `200` / `401` | ✅ |
| P27 | Login con email inexistente vs. contraseña incorrecta | Mismo mensaje | Ambos `401 "Credenciales o código inválido."` | ✅ |
| P28 | Lockout (6 intentos, solo la cuenta de prueba) | Bloqueo | Intentos 1-5 → `401`; intento 6 → **`423`**; con la contraseña correcta durante el bloqueo → `423`. La cuenta quedó bloqueada 15 min (avisado). | ✅ (con H-07) |
| P29 | Rate limit por IP en el login | 429 tras 10/min | [NO VERIFICABLE]: exigiría más de 10 intentos (regla de máximo ~6). Revisado en código: `auth/service.py:143-149`, `core/client_ip.py:35-65` | — |
| P30 | Flujo E2E: envío → polling → reporte | done | [NO VERIFICABLE]: sin créditos de LLM, por decisión del usuario | — |
| P31 | Worker vivo | Procesando | Logs: `Starting worker for 2 functions: ping, run_pipeline`, `redis_version=8.2.10 … db_keys=0`, `worker_startup`. Ningún trabajo procesado en la ventana observada. | ⚠️ |
| P32 | Postgres y Redis públicos | No | `tcpProxies: []` en los tres servicios; `DATABASE_URL` y `REDIS_URL` → `*.railway.internal` | ✅ |
| P33 | `ENVIRONMENT` | production | `production` (además: docs 404, HSTS y cookies Secure) | ✅ |
| P34 | Migraciones | Head del repo | El pre-deploy `alembic upgrade head` corre sin "Running upgrade" (ya estaba en head). Revisión exacta [NO VERIFICABLE] sin acceso a la BD. | ✅ [PROBABLE] |
| P35 | Reputación en producción | Actualizándose | `GET /sources`: 16 fuentes, **`cases_count = 0` en todas**; el score sigue en los priors | ⚠️ (nunca se procesó un caso) |
| P36 | `/sources/{domain}` en la web | Página de detalle | `GET /sources/reuters.com` → **404**; la API sí lo sirve (`/api/sources/x` → 404 JSON solo si no existe) | ❌ (H-10) |
| P37 | Tiempos | — | Login aprox. 0.27 s, verify aprox. 0.22 s, confirm 0.94 s, HTML de la web aprox. 0.3 s | ✅ |

## 5. Diferencias entre el código y el despliegue

| # | Repo | Producción | Evidencia |
|---|---|---|---|
| D1 | `railway.toml:9-10` declara `healthcheckPath = "/health/ready"` y `healthcheckTimeout = 300` | El manifiesto del deploy `21404ea` de la API tiene `healthcheckPath: None` y `healthcheckTimeout: None`; Railway no aplica el healthcheck | `railway deployment list --json` → `serviceManifest.deploy` [CONFIRMADO] |
| D2 | `apps/api/railway.worker.toml` define el worker | `railwayConfigFile: null`; el worker se configura a mano en el dashboard (start command), así que el archivo del repo no se usa | GraphQL `serviceInstance` [CONFIRMADO]. Hoy en la madrugada esto provocó deploys atascados con el worker en el pre-deploy. |
| D3 | `.env.example` lista ~30 variables | En la API solo se definen 11; el resto usa los defaults de `config.py` (aceptable) | `railway variables` (solo nombres) |
| D4 | README: "usuario demo con 2FA + casos de ejemplo" | `seed_demo.py` se niega a correr con `ENVIRONMENT=production`; ninguna fuente tiene casos, lo que indica que no hay casos sembrados ni reales | `apps/api/app/cli/seed_demo.py:1-22`; P35 [PROBABLE] |
| D5 | Preview y producción en Vercel | `API_PROXY_TARGET` (preview y development) apunta a la **API de producción** | Vercel env [CONFIRMADO] |
| D6 | Railway Config-as-Code | El CLI avisa que `railway.toml` deja de funcionar el **2026-12-01** | Salida de `railway` CLI 5.63.4 |

## 6. Criterios de aceptación

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Desplegado y accesible, front↔back, worker procesando, demo lista | **Parcial** | ✅ web y API responden (P1, P17); el proxy `/api` funciona (P12, P17); el worker está vivo (P31). ❌ no se vio ningún trabajo procesado, no hay créditos de LLM y el usuario demo y los casos no están en producción (D4). |
| 2 | Ninguna ruta protegida accesible solo con la contraseña (API desplegada) | **Fallido** | P17: una cuenta recién registrada (2FA desactivada por defecto) obtiene `200 authenticated` y accede a `/auth/me` y `/submissions`. Es intencional: `auth/routers.py:164-167` y el commit `b2f2539`. Con 2FA activada sí se cumple (P21). |
| 3 | Texto → afirmaciones, veredictos con citas reales y scores idempotentes (caso real) | **No verificable** | Sin créditos de LLM. En código: `orchestrator.py:65-127`, `verify.py:170-194`, `reputation.py:119-127` con `UNIQUE(source_id, claim_id)` en `sources/models.py:33`; con tests con mocks. |
| 4 | Ningún veredicto sin evidencia válida como SUPPORTED/CONTRADICTED | **Parcial** | ✅ con cero evidencia validada se fuerza INSUFFICIENT (`verify.py:187-190`, tests `test_verify_claim_drops_hallucinated_evidence` y `…outside_whitelist`). ❌ un SUPPORTED puede quedar sostenido solo por evidencia `neutral` o `contradicts`, porque el veredicto no se reconcilia con la postura (`verify.py:192-194`), y el snippet lo escribe el LLM sin validarlo (`verify.py:180`). No hay caso real que verificar. |
| 5 | Ningún secreto en el repo, los logs o el bundle | **Aprobado** | Escaneo manual del historial; los logs de producción no contienen `sk-ant`, `eyJhbGci` ni passwords (0 coincidencias); bundle limpio (P12). Las constantes de desarrollo públicas están bloqueadas en producción (`config.py:127-167`). |

## 7. Hallazgos detallados

### Crítica
No se confirmó ninguna. No hubo acceso a datos de terceros ni ejecución de código.

### Alta

**H-01 · A · La 2FA es opcional: sesión completa solo con contraseña** [CONFIRMADO]
- **Evidencia:**
  - `apps/api/app/modules/auth/routers.py:164-167`: si `not user.mfa_enabled`, emite la sesión directamente.
  - El test `tests/auth/test_auth_flow.py:98` lo fija como comportamiento esperado.
  - Producción: `POST /api/auth/login` → `200 {"status":"authenticated"}`, `Set-Cookie: access_token=eyJh...****; HttpOnly; Secure`, y luego `GET /api/auth/me` → `200` (P17).
- **Impacto:** incumple el criterio 2 y la premisa de "autenticación de dos pasos". Un password filtrado basta para entrar en cualquier cuenta sin TOTP, que es el estado por defecto de toda cuenta nueva.
- **Recomendación:** decidirlo con el equipo.
  - (a) Volver a la 2FA obligatoria: tras el login sin 2FA, emitir un token `mfa_setup_pending` que solo permita `/2fa/setup` y `/2fa/confirm`.
  - (b) Si se mantiene opcional, cambiar el criterio y el texto de producto, y forzar la 2FA al menos antes de enviar casos (que es lo que cuesta dinero).
- Requiere redespliegue de la API y la web.

**H-02 · B/G · Sin control de costos del LLM ni cuotas por usuario** [CONFIRMADO en código; impacto PROBABLE]
- **Evidencia:**
  - `submissions/routers.py:31-41` y `submissions/service.py:14-29`: no hay rate limit, cuota ni tope diario. El registro es abierto (`auth/routers.py:133`).
  - Cada caso dispara hasta 3 intentos de extracción (`claims.py:49`) más hasta 8 afirmaciones × 2 intentos × 5 búsquedas web con `max_tokens=4096` (`verify.py:14-15`, `:123`, `:138`).
  - Railway: `Soft limit: not set`, `Hard limit: not set` (`railway usage`). El límite de gasto en Anthropic es [NO VERIFICABLE].
- **Impacto:** un script con una cuenta gratuita puede encolar miles de casos y agotar el presupuesto, o denegar el servicio al agotar los créditos (que es el estado actual).
- **Recomendación:**
  - Rate limit por usuario e IP en `POST /submissions` reutilizando `check_rate_limit`, más una cuota diaria persistida.
  - Tope de casos en vuelo por usuario.
  - Límite de gasto en la consola de Anthropic y hard limit en Railway.
- Redespliegue de la API más una variable nueva (p. ej. `MAX_SUBMISSIONS_PER_DAY`).

**H-03 · B · SSRF por redirecciones y DNS rebinding en la ingesta de URL** [CONFIRMADO en código]
- **Evidencia:** `pipeline/url_safety.py:32-36` lo admite. `ingest.py:32-33` valida y luego `trafilatura.fetch_url(url)` resuelve de nuevo y sigue redirecciones.
- **Impacto:** un servidor público puede responder 302 hacia `http://*.railway.internal:…` o hacia rangos internos, y el contenido extraído termina en `extracted_text`, que se envía al LLM y se persiste. En Railway, Postgres y Redis no hablan HTTP (impacto acotado), pero cualquier servicio HTTP interno sería alcanzable.
- **Recomendación:** descargar con httpx usando `follow_redirects=False` y revalidar cada salto (máx. 3), fijar la IP resuelta para la conexión, limitar el tamaño de la respuesta, y pasar el HTML a `trafilatura.extract`. Redespliegue del worker.

**H-04 · B · Casos colgados para siempre por el timeout de arq y caídas del worker** [PROBABLE]
- **Evidencia:**
  - `workers/arq_settings.py:28-32` no define `job_timeout`; el default de arq es 300 s (`Worker.__init__`: `job_timeout=300, max_tries=5`).
  - `orchestrator.py:128` captura `Exception`, pero la cancelación por timeout es `asyncio.CancelledError` (BaseException), así que el estado queda en `transcribing`, `verifying`…
  - No hay ningún reaper de casos atascados.
  - Si el worker muere (OOM), arq reintenta y `run_pipeline` vuelve a insertar `Claim` sin limpiar los anteriores (`orchestrator.py:91-98`). Resultado: claims duplicados y doble puntuación de reputación con claim_ids nuevos.
- **Impacto:** la UI hace polling indefinido (`app/reports/[id]/page.tsx:72-74`) y la reputación se contamina.
- **Recomendación:**
  - `job_timeout` explícito por tipo de entrada.
  - `try/finally` que marque `failed` también ante `CancelledError`.
  - Al iniciar el job, si ya hay claims, borrarlos o abortar (idempotencia por `submission_id`).
  - Un cron de arq que marque `failed` los casos sin progreso en N minutos.
  - Un timeout máximo de polling en la web.

**H-05 · B · La transcripción de video es probablemente inviable en el worker de producción** [PROBABLE]
- **Evidencia:**
  - Límite del worker: **1024 MB**, con un pico observado de 1004 MB (`railway metrics -s upbeat-wholeness`).
  - `faster-whisper small` int8 en CPU (`transcribe.py:28`) más yt-dlp y la app.
  - El modelo se instancia en cada trabajo (`orchestrator.py:61`), así que se descarga y carga en cada caso.
  - `ingest.py:81-86` solo limita la duración si yt-dlp la conoce (`duration is None` → sin límite, p. ej. en directos); no hay límite de tamaño de archivo en `_download_audio` (`ingest.py:64-70`).
  - El README admite que el video no se probó de punta a punta.
- **Impacto:** OOM, timeouts (H-04) o disco temporal lleno.
- **Recomendación:** cachear el modelo a nivel de proceso (en `startup`), usar `tiny` o `base` o una API de transcripción, rechazar `duration is None`, añadir `max_filesize` y `match_filter` a yt-dlp, y subir la memoria o deshabilitar el video en producción hasta probarlo.

### Media

**H-06 · A · Enumeración de usuarios en el registro** [CONFIRMADO]
- **Evidencia:** `auth/routers.py:139-140`; P16 `409 "Ese correo ya está registrado."`.
- **Recomendación:** respuesta genérica ("si el correo es válido, recibirás instrucciones") con verificación por email, o al menos un rate limit en `/register` (hoy no tiene ninguno).

**H-07 · A · El lockout revela qué cuentas existen y permite bloquear cuentas ajenas** [CONFIRMADO]
- **Evidencia:**
  - `auth/routers.py:159-160` (`423`) frente a `401`. El chequeo de bloqueo ocurre antes del hash (`service.py:155-156`): logs con `status=423 duration_ms=6.9` frente a aprox. 250 ms del 401.
  - Cualquiera puede bloquear una cuenta ajena 15 min con 5 intentos (`service.py:95-99`).
  - Documentado en el README ("Limitaciones").
- **Recomendación:** devolver `401` también durante el bloqueo, ejecutar el hash dummy, y preferir un backoff progresivo por usuario+IP a un bloqueo duro.

**H-08 · D · El veredicto no se reconcilia con la evidencia y el snippet no se valida** [CONFIRMADO en código]
- **Evidencia:**
  - `verify.py:192-194` devuelve el `verdict` del LLM aunque toda la evidencia validada sea `neutral` o tenga la postura opuesta.
  - `verify.py:180` toma el `snippet` del LLM; solo se valida la URL (`:172`).
- **Impacto:** puede mostrarse un SUPPORTED con citas que no lo respaldan (criterio 4 parcial).
- **Recomendación:** SUPPORTED exige al menos una evidencia `supports` y CONTRADICTED al menos una `contradicts`; si no, INSUFFICIENT. Comparar el snippet con el `encrypted_content`/`title` del resultado o marcarlo como "resumen del modelo". Añadir tests.

**H-09 · E/G · La web no envía cabeceras de seguridad** [CONFIRMADO]
- **Evidencia:** `apps/web/next.config.ts:5` (config vacía); P5.
- **Impacto:** clickjacking de `/settings/security` (desactivar 2FA requiere código, lo que mitiga) y ausencia de una segunda barrera ante XSS.
- **Recomendación:** `headers()` en `next.config.ts` con CSP (`default-src 'self'; frame-ancestors 'none'; img-src 'self' data:`…), `X-Content-Type-Options`, `Referrer-Policy` y `Permissions-Policy`. Redespliegue de la web.

**H-10 · E/C · Falta la página `/sources/[domain]`** [CONFIRMADO]
- **Evidencia:** rutas del build (sección 3) sin `/sources/[domain]`; P36 `404`. La API sí expone el intervalo y el historial (`sources/routers.py:37-57`), pero la UI no los muestra.
- **Recomendación:** crear la página con score, intervalo, `cases_count`, `low_sample` y `recent_events`, y enlazarla desde el reporte.

**H-11 · C · La actualización de reputación no es atómica bajo concurrencia** [CONFIRMADO en código]
- **Evidencia:** `reputation.py:119-136` hace un read-modify-write de `alpha/beta` sin `SELECT … FOR UPDATE`; el worker ejecuta hasta 10 jobs en paralelo (arq `max_jobs=10`). El chequeo previo más `UNIQUE` evita el doble evento, pero un `IntegrityError` en carrera aborta el commit entero y el caso termina `failed` con los claims ya guardados (`orchestrator.py:119-125`).
- **Recomendación:** `UPDATE sources SET alpha = alpha + 1 …` atómico, o un `with_for_update()`, más `INSERT … ON CONFLICT DO NOTHING` para el evento.

**H-12 · A · El token `mfa_pending` se puede reutilizar** [CONFIRMADO]
- **Evidencia:** P23. Tras un `/2fa/verify` exitoso, el mismo token emitió otra sesión (con un código de recuperación). No se registra el `jti` (`service.py:171-175`, `routers.py:99-115`).
- **Impacto:** bajo, porque sigue haciendo falta un segundo factor válido; es higiene de un solo uso.
- **Recomendación:** guardar el `jti` en Redis con TTL y rechazar su reutilización.

**H-13 · B · Texto interno de excepciones expuesto al usuario** [CONFIRMADO en código]
- **Evidencia:** `orchestrator.py:49` (`rationale=f"No se pudo verificar…: {exc}"`), `:133` (`error=str(exc)`), devuelto en `submissions/routers.py:26`; `claims.py:75-77` incluye el error del SDK.
- **Impacto:** fuga de detalles del proveedor o la red en la UI y en reportes persistentes.
- **Recomendación:** mensajes genéricos al usuario y el detalle solo en los logs con el `request_id`/`submission_id`.

**H-16 · G · Sin CI, sin staging, y previews contra producción** [CONFIRMADO]
- **Evidencia:** no hay `.github/workflows` ni otro CI. Railway despliega cada push a `main` sin ejecutar tests. En Vercel, `API_PROXY_TARGET` de preview apunta a la API de producción (D5).
- **Recomendación:** GitHub Actions con pytest, ruff, eslint, tsc y build como check obligatorio; entorno `staging` en Railway; previews contra staging.

**H-18 · G · Healthcheck no aplicado, worker sin config versionada, contenedores como root** [CONFIRMADO]
- **Evidencia:** D1 y D2; `apps/api/Dockerfile` y `apps/web/Dockerfile:17-30` sin `USER`.
- **Recomendación:** fijar `railwayConfigFile` en ambos servicios (o migrar a `.railway/railway.ts` antes del 2026-12-01), `USER` no root, y fijar las imágenes base por digest.

**H-19 · G · Observabilidad y recuperación mínimas** [CONFIRMADO / NO VERIFICABLE]
- **Evidencia:** solo logs JSON (bien hechos: `core/logging.py`); sin alertas, sin métricas de cola, sin monitor de jobs colgados. Los backups de Postgres en plan trial son [NO VERIFICABLE] (no se vio configuración de backups). Hay logs de acceso duplicados (uvicorn más structlog).
- **Recomendación:** activar backups (plan de pago), alertas de Railway por crash y memoria, métrica o alerta de casos en estado no terminal más de 10 min, y desactivar el access log de uvicorn.

### Baja

**H-14 · G · Valores de desarrollo y credencial demo versionados** [CONFIRMADO]
- **Evidencia:** `core/config.py:8-9` (JWT dev y clave Fernet dev) y `cli/seed_demo.py:46` (`DEMO_PASSWORD`). Mitigado: producción se niega a arrancar con esos valores (`config.py:127-167`) y el seed se niega en producción.
- **Recomendación:** mantener el bloqueo; generar la contraseña demo aleatoria por ejecución.

**H-15 · A/E · Token `mfa_pending` en `sessionStorage`** [CONFIRMADO]
- **Evidencia:** `apps/web/lib/auth.ts:33-45`. Dura 5 min y por sí solo no da sesión.
- **Recomendación:** moverlo a una cookie HttpOnly de path `/api/auth/2fa` con SameSite=Strict.

**H-17 · A · Las respuestas 422 repiten la entrada** [CONFIRMADO]
- **Evidencia:** P13 (default de FastAPI): un password de más de 256 caracteres se devuelve en `input`.
- **Recomendación:** handler de `RequestValidationError` que omita `input` en las rutas de auth.

**H-20 · F · Imports cruzados de modelos entre módulos** [CONFIRMADO]
- **Evidencia:** `reports/service.py:14,24` importa `pipeline.models` y `sources.models`; `pipeline/orchestrator.py:15` importa `submissions.models`; `core/deps.py:10` y `submissions/routers.py:9` importan `auth.models.User`. Contradice la regla del propio repo (`sources/reputation.py:3-9`).
- **Recomendación:** exponer lecturas vía funciones `service` de cada módulo.

**H-21 · C/B · Evidencia de subdominios descartada** [CONFIRMADO en código]
- **Evidencia:** `verify.py:174-176` exige coincidencia exacta tras `normalize_domain` (`sources/service.py:10-19`, que solo quita `www.`). `news.un.org` o `edition.cnn.com` no coinciden con `un.org`, lo que produce INSUFFICIENT falsos.
- **Recomendación:** aceptar subdominios del dominio registrado en la lista blanca.

**H-22 · A · Detalles menores de auth** [CONFIRMADO]
- **Evidencia:**
  - La comparación CSRF con `!=` no es de tiempo constante (`core/deps.py:46`).
  - El access token sigue válido hasta 15 min tras el logout o el reuso (stateless).
  - El refresh rotation no bloquea la fila (`service.py:346-389`): dos refresh simultáneos pueden ganar ambos. La web lo mitiga con `refreshInFlight` (`lib/api.ts:34-52`).
- **Recomendación:** `hmac.compare_digest`; denylist de `jti` opcional; `with_for_update()`.

**H-23 · G · `pnpm audit`: 3 high en tooling** [CONFIRMADO]
- **Evidencia:** sección 3; `shadcn` está en `dependencies` (`apps/web/package.json:22`).
- **Recomendación:** mover `shadcn` a `devDependencies` y actualizar `next`/`postcss`.

**H-24 · H · `ruff format` falla y la cobertura está mal medida** [CONFIRMADO]
- **Recomendación:** formatear `tests/sources/test_reputation.py`; añadir `[tool.coverage.run] concurrency = ["greenlet", "thread"]`.

## 8. Cosas bien hechas

**Hashing y tiempos**
- argon2id con parámetros por defecto de argon2-cffi (`t=3, m=64 MiB, p=4`, comprobado), y hash dummy contra la enumeración por tiempo (`core/security.py:19-49`).
- Política de contraseña de 10+ caracteres con mayúscula, minúscula y dígito (`security.py:52-66`), comprobada en vivo.

**TOTP y recuperación**
- Secreto TOTP cifrado con Fernet (`security.py:107-120`), ventana ±1 y protección contra reutilización con `totp_last_used_step` (`auth/totp.py:46-65`), comprobado en vivo (P22).
- El reenrolamiento no reemplaza el dispositivo hasta confirmarse (`auth/models.py:22-25`, `service.py:214-219`).
- Códigos de recuperación generados con `secrets`, hasheados con argon2, de un solo uso y mostrados una sola vez (`recovery_codes.py`, `service.py:222-228`, P26).
- Desactivar la 2FA exige un código, no basta la sesión (`routers.py:249-282`).

**Sesiones y CSRF**
- Refresh opaco rotativo con detección de reutilización y revocación de familia (`service.py:346-389`), comprobado en vivo (P24).
- CSRF de doble envío en todas las mutaciones, comprobado en vivo (P20, P25).
- Mensajes de error genéricos (`GENERIC_AUTH_ERROR`).

**IP del cliente**
- Resolución robusta detrás de proxies: secreto compartido con la web y conteo de hops desde la derecha (`core/client_ip.py`), con tests (`tests/core/test_client_ip.py`).

**Configuración de producción**
- Fail-fast con secretos débiles o CORS `*` (`config.py:127-167`).
- Docs desactivadas en producción (`main.py:40-49`), cabeceras de seguridad, `no-store` y 500 genérico con `request_id` (`core/middleware.py`).
- Logging estructurado con redacción de claves sensibles (`core/logging.py:6-27`); 0 secretos encontrados en los logs de producción.

**Pipeline de IA**
- Defensas anti-alucinación deterministas: URL presente en los `web_search_result` reales y dominio en la lista blanca (`verify.py:89-103`, `:170-185`).
- Delimitadores `<document>` y `<claim>` con instrucción explícita contra la inyección (`claims.py:22-25`, `verify.py:47-51`).
- Salida validada con Pydantic, reintentos, concurrencia limitada con semáforo, timeout por afirmación y fallos parciales que no tumban el lote (`orchestrator.py:30-51`).

**Reputación**
- Beta-Bernoulli correcta, con piso `MIN_WEIGHT`, al menos 2 grupos independientes, deduplicación por `syndication_group`, exclusión de `neutral` e INSUFFICIENT, y `UNIQUE(source_id, claim_id)` (`reputation.py`, `sources/models.py:33`). Tests al 98%.
- `docs/reputation.md` documenta honestamente la circularidad y el conformismo.

**Autorización de recursos**
- IDOR evitado: `get_submission` filtra por `user_id` y un caso ajeno es indistinguible de uno inexistente (`submissions/service.py:32-41`, `reports/service.py:44-48`), con el test `test_report_of_another_user_is_404`.

**Frontend**
- Sin `dangerouslySetInnerHTML`; enlaces externos con `rel="noopener noreferrer nofollow"` (`app/reports/[id]/page.tsx:345-346`).
- TypeScript estricto, polling con limpieza y estados de error.
- Textos de producto que evitan "verdadero/falso" (`components/verdict.tsx:15-43`, `reports/service.py:27-32`).

**Infraestructura**
- Postgres y Redis sin exposición pública (P32); Redis con `--requirepass`.
- Secretos solo en los gestores de Railway y Vercel (`API_PROXY_SECRET` como *sensitive*).

## 9. Plan de remediación priorizado

### (a) Imprescindible antes de la demo
| # | Acción | Hallazgo | Esfuerzo | Redespliegue / variables |
|---|---|---|---|---|
| a1 | Cargar créditos de LLM y fijar un **límite de gasto** en Anthropic y un hard limit en Railway | H-02 | S | Consola del proveedor |
| a2 | Rate limit y cuota en `POST /submissions` | H-02 | S | API + variable nueva |
| a3 | Decidir la 2FA: obligatoria (token `mfa_setup_pending`) o actualizar el criterio y la copia | H-01 | M | API + web |
| a4 | Usuario demo y casos en producción: seed seguro para producción (contraseña aleatoria, ejecución manual con `railway run`) o sembrar casos reales | criterio 1 | S | Comando único |
| a5 | Marcar `failed` ante `CancelledError`, `job_timeout` explícito y timeout de polling en la UI | H-04 | S | API, worker, web |
| a6 | Deshabilitar `input_type=video` en producción hasta probarlo | H-05 | S | API (flag o variable) |
| a7 | Plan B de demo: video o capturas de un caso completo y casos sembrados | H | S | — |

### (b) Antes de un piloto con usuarios reales
| # | Acción | Hallazgo | Esfuerzo | Redespliegue / variables |
|---|---|---|---|---|
| b1 | SSRF: descarga propia sin redirecciones automáticas, revalidación por salto, IP fijada y límite de tamaño | H-03 | M | Worker |
| b2 | Reconciliar el veredicto con la postura y validar el snippet | H-08 | S | Worker |
| b3 | Idempotencia de `run_pipeline` y reaper de casos colgados | H-04 | M | Worker |
| b4 | Reputación atómica (`UPDATE … +1`, `ON CONFLICT`) | H-11 | S | Worker |
| b5 | Cabeceras de seguridad en la web | H-09 | S | Web |
| b6 | Registro y lockout genéricos (sin 409 ni 423), rate limit en `/register` | H-06, H-07 | S | API |
| b7 | `mfa_pending` de un solo uso, y en cookie en lugar de sessionStorage | H-12, H-15 | S | API + web |
| b8 | Mensajes de error genéricos al usuario | H-13 | S | Worker |
| b9 | CI (pytest, ruff, eslint, tsc, build) como check obligatorio; staging y previews contra staging | H-16 | M | Vercel env |
| b10 | `railwayConfigFile` explícito en ambos servicios y healthcheck efectivo; migrar a `.railway/railway.ts` antes del 2026-12-01 | H-18, D1, D2 | S | Railway |
| b11 | Backups de Postgres y alertas (crash, memoria, casos atascados) | H-19 | S | Railway (plan de pago) |
| b12 | Página `/sources/[domain]` | H-10 | S | Web |

### (c) Mejoras futuras
| # | Acción | Hallazgo | Esfuerzo |
|---|---|---|---|
| c1 | Whisper cacheado por proceso, modelo menor o API de transcripción; worker dedicado a video | H-05 | M |
| c2 | Aceptar subdominios de la lista blanca | H-21 | S |
| c3 | Eliminar los imports cruzados de modelos | H-20 | M |
| c4 | Contenedores sin root e imágenes por digest | H-18 | S |
| c5 | `compare_digest` en CSRF, denylist de access tokens, bloqueo de fila en el refresh | H-22 | S |
| c6 | `shadcn` a devDependencies, actualizar dependencias | H-23 | S |
| c7 | Configurar coverage para greenlet, `ruff format` e integración en CI con servicios | H-24 | S |
| c8 | Omitir `input` en los 422 de auth | H-17 | S |

## 10. Limitaciones de esta auditoría

- **Pipeline con LLM, E2E y criterio 3:** no se envió ningún caso porque no había créditos. La extracción, la verificación, la idempotencia en vivo de la reputación y los tiempos del flujo se evaluaron solo por código y tests con mocks.
- **Rate limit por IP del login:** no se probó en vivo; requería más de 10 intentos y la regla limita a unos 6. Se revisó en código.
- **IDOR:** solo por revisión de código y tests. Con una única cuenta no hay recursos ajenos con los que probar de forma segura.
- **`mfa_setup_pending`:** ese alcance ya no existe en el código (el enrolamiento requiere sesión completa desde `b2f2539`); se probó en su lugar el `mfa_pending`.
- **Usuario demo en producción:** no se intentó entrar con las credenciales demo del repo. Sería acceder a una cuenta distinta de la de prueba (regla 2). Su ausencia se infiere de que el seed se niega a correr en producción y de `cases_count = 0` [PROBABLE].
- **Tests de integración y gitleaks:** no se ejecutaron porque Docker Desktop no estaba corriendo. El escaneo de secretos se hizo a mano sobre las 20 revisiones del historial.
- **Base de datos:** sin acceso directo, así que la revisión de Alembic aplicada y la existencia de backups no se verificaron.
- **Límite de gasto de Anthropic:** no hay acceso a la consola del proveedor.
- **Rendimiento:** se midieron tamaños y tiempos de respuesta, pero no Core Web Vitals.
- **Accesibilidad:** revisión estática (atributos `aria-*`, `lang="es"`, viewport); no se ejecutó una auditoría automática.
- **Cuenta de prueba:** `audit-634ff5fd@example.com` sigue existiendo en producción con TOTP activo; quedó bloqueada 15 min por la prueba de lockout. Sus credenciales están solo en el scratchpad local de esta sesión, fuera del repo. Se recomienda borrarla de la tabla `users`; el borrado en cascada elimina sus códigos y refresh tokens.
