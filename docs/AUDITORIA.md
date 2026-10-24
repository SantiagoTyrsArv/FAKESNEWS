# Auditoría técnica — FakesNews

- **Fecha:** 2026-10-23
- **Código auditado:** rama `feat/motion`, commit `ce7ab30`. Las rutas y números de línea se refieren a ese commit. Mientras se hacía la auditoría, la Tarea 5 del plan de animaciones estaba modificando páginas de `apps/web`, así que algunas líneas del frontend pueden haberse movido.
- **Modo:** solo lectura. No se modificó ningún archivo del proyecto, salvo la creación de este documento.
- **Herramientas ejecutadas:**
  - OSV-Scanner 2.7.0: `osv-scanner scan source -r .`
  - En `apps/api`: `pytest` con cobertura, `ruff check` y `ruff format --check`
  - `pnpm outdated` y `uv tree --outdated`
- **Cómo se verificó:**
  - El uso del SDK de Anthropic se contrastó con la documentación de referencia del SDK.
  - La configuración de Next 16 se contrastó con la guía local en `apps/web/node_modules/next/dist/docs/`.
- **Antecedentes:**
  - `docs/AUDIT.md` (2026-10-07) es una auditoría anterior de código y producción. Varios de sus hallazgos ya están corregidos (cuotas de casos, `ruff format`, CI de la web).
  - `VULNERABILIDADES.md` documenta la corrección de dependencias del commit `bb65053`. Es un informe local que no se versiona.

> **Estado al 2026-10-24:** el plan de acción se ha ido aplicando desde que se escribió este documento. La [sección 7](#7-estado-del-plan-de-acción-2026-10-24) indica qué está hecho, en qué PR, y qué sigue abierto. El resto del documento describe el código tal como estaba en `ce7ab30`.

---

## 1. Resumen ejecutivo

**Estado general: bueno para un MVP, todavía no listo para producción seria.** El código es limpio, está tipado y documentado, y la seguridad de autenticación está muy por encima de la media: argon2id, rotación de refresh con detección de reutilización, CSRF de doble envío, TOTP anti-replay y fail-fast con secretos débiles. La anti-alucinación del pipeline es determinista: una cita solo pasa si su URL salió de la búsqueda real y su dominio está en la lista blanca.

Los riesgos reales están en otras capas:

1. **Concurrencia en la base de datos.** Varias operaciones leen, modifican y escriben sin bloqueo de fila: la reputación, la rotación del refresh token, los códigos de recuperación y las cuotas. Los tests usan SQLite, así que nunca lo detectarían.
2. **DevOps.**
   - La API no tiene CI.
   - Las imágenes corren como root y llevan dependencias de desarrollo.
   - La web no envía cabeceras de seguridad.
3. **Uso del LLM.** `max_tokens` es bajo para un modelo que piensa por defecto (Sonnet 5), no se maneja `pause_turn` ni `refusal`, y el SSRF por redirecciones sigue abierto.

| # | Área | Nota (1–10) | Resumen |
|---|---|---:|---|
| 1 | Arquitectura y estructura | 8 | Monolito modular claro (módulos con `models/schemas/service/routers`), límites documentados; algunos imports cruzados y skills duplicadas en el repo. |
| 2 | Uso de frameworks | 7 | FastAPI, SQLAlchemy 2 async y Next 16 usados de forma idiomática (`proxy.ts`, `Annotated`, `lifespan`); la web es 100 % componentes cliente y el LLM no aprovecha bien el SDK. |
| 3 | Dependencias y vulnerabilidades | 7 | Lockfiles congelados y overrides de seguridad. Quedan 2 avisos nuevos, ambos transitivos y no explotables. `shadcn` está en dependencias de producción y hay versiones mayores atrasadas. |
| 4 | Calidad de código | 8 | Nombres claros, errores de dominio tipados, ruff limpio. Hay algo de código muerto, `except Exception` amplios y manejo de 401 repetido en cada página. |
| 5 | Seguridad | 7 | Auth excelente. SSRF por redirecciones y DNS rebinding, web sin CSP ni cabeceras, e imágenes como root. |
| 6 | Base de datos y datos | 6 | Modelo y migraciones correctos. Carreras sin bloqueo, sin índices compuestos, estados como texto libre y sin paginación. |
| 7 | Rendimiento | 6 | argon2 bloquea el event loop, Whisper se recarga en cada caso, hay N+1 menores y la sesión de BD queda retenida durante las llamadas al LLM. Lighthouse móvil: 91 (LCP 3,5 s). |
| 8 | Testing | 6 | 141 tests pasan (84 % de cobertura) y los de dominio son de buena calidad. Pero corren sobre SQLite, la web no tiene tests funcionales y no hay e2e. |
| 9 | DevOps y configuración | 5 | Configuración tipada, healthchecks y logging JSON. Sin CI de API, sin escaneo de dependencias en CI, sin `standalone`, sin `USER` y sin monitoreo ni alertas. |
| 10 | Documentación | 7 | README raíz muy completo y honesto (limitaciones, despliegue); `apps/web/README.md` es el de plantilla y no hay runbook. |

**Nota media: 6,7 / 10.**

---

## 2. Stack detectado

| Capa | Tecnología | Versión exacta (lockfile) |
|---|---|---|
| Lenguaje API | Python | 3.12 (`requires-python >=3.12,<3.13`) |
| Framework API | FastAPI / Starlette / Uvicorn | 0.141.1 / 1.7.0 / 0.54.0 |
| Validación | Pydantic / pydantic-settings / email-validator | 2.13.5 / 2.15.0 / 2.3.0 |
| ORM y migraciones | SQLAlchemy (async) / asyncpg / Alembic | 2.1.1 / 0.31.0 / 1.20.0 |
| Base de datos | PostgreSQL | 16-alpine (compose) |
| Cola | Redis / redis-py / arq | 7-alpine / 5.3.1 / 0.28.0 |
| Auth | argon2-cffi / PyJWT / pyotp / cryptography / qrcode | 25.1.0 / 2.15.1 / 2.10.0 / 50.0.1 / 8.2 |
| LLM | anthropic (SDK Python), modelo `claude-sonnet-5` | 1.9.0 |
| Ingesta | trafilatura / yt-dlp / faster-whisper (ctranslate2, av) | 2.2.0 / 2026.8.19 / 1.2.1 (4.8.2, 18.1.0) |
| Utilidades | httpx / tenacity / structlog / python-multipart | 0.28.1 / 9.1.4 / 26.1.0 / 0.0.32 |
| Calidad API | ruff / pytest / pytest-asyncio / pytest-cov / respx / aiosqlite | 0.16.9 / 9.1.1 / 1.4.0 / 7.1.0 / 0.23.1 / 0.22.1 |
| Gestor API | uv | 0.12.3 en la imagen (local 0.13.5) |
| Framework web | Next.js (App Router, `proxy.ts`) / React | 16.4.2 / 19.2.8 |
| Lenguaje web | TypeScript (strict) | 5.9.3 |
| UI | Tailwind / shadcn / @base-ui/react / `cn` / lucide-react / sonner / next-themes | 4.3.3 / 4.22.1 / 1.8.0 / 0.4.0 / 1.48.0 / 2.0.8 / 0.4.6 |
| Motion | gsap / lenis / animate.css / tw-animate-css | 3.15.0 / 1.3.27 / 4.1.1 / 1.4.0 |
| Calidad web | ESLint (+ eslint-config-next) / Stylelint / `node --test` | 9.39.5 (16.4.2) / 17.16.0 |
| Gestor web | pnpm | 11.22.0 (Node 22 en Docker/CI, 24 en local) |
| Infra | Docker / docker-compose / Railway (api, worker) / Vercel (web) | — |
| CI | GitHub Actions: solo `.github/workflows/web.yml` | — |

**Arquitectura:**
- `apps/web` (Next) habla con `apps/api` (FastAPI) mediante cookies httpOnly y CSRF.
- La API encola en Redis y el worker arq ejecuta el pipeline `ingest → transcribe → claims → verify → scoring`.
- El pipeline usa Claude con `web_search` restringido a 16 dominios de confianza y persiste en Postgres.
- La reputación de las fuentes es Beta-Bernoulli.

---

## 3. Resultados de OSV-Scanner

`osv-scanner scan source -r .` revisó 98 paquetes PyPI (`apps/api/uv.lock`) y 725 de npm (`apps/web/pnpm-lock.yaml`), y encontró **2 paquetes con 6 avisos**. Ambos son transitivos y salieron después de la corrección documentada en `VULNERABILIDADES.md`.

| Paquete | Versión | ID | Alias | Severidad (CVSS) | Corregida en | Lo trae | ¿Explotable en este proyecto? |
|---|---|---|---|---|---|---|---|
| `undici` | 7.30.0 | GHSA-xjj6-f33q-929c | CVE-2026-109869 | 🟠 Alta (7.5) | 7.30.1 | `shadcn` 4.22.1 (CLI), `@shadcn/registry`, `@dotenvx/dotenvx` | **No en la práctica.** DoS al recibir respuestas con demasiadas `content-encoding`. Solo lo usa el CLI de shadcn al descargar del registro; la app en ejecución no importa `undici` (Next usa su propio fetch). |
| `undici` | 7.30.0 | GHSA-4qv8-2p9j-2685 | CVE-2026-109924 | 🟡 Media (5.9) | 7.30.1 | ídem | **No.** El parser de EventSource no se usa en ningún código del proyecto. |
| `undici` | 7.30.0 | GHSA-f72v-6w45-q472 | CVE-2026-109841 | 🟡 Media (5.9) | 7.30.1 | ídem | **No.** El bypass de SRI no aplica: no hay `fetch` con `integrity` en el runtime. |
| `filelock` | 4.0.6 | GHSA-v4x8-3wr5-3wq8 | CVE-2026-112940 | 🟠 Alta (7.1) | 4.2.1 | `huggingface-hub` 1.33.0 (vía faster-whisper) | **No en la práctica.** Afecta a `ReadWriteLock` sobre SQLite con un atacante local que planta symlinks. huggingface-hub usa `FileLock` al descargar el modelo Whisper, en un contenedor sin otros usuarios. |
| `filelock` | 4.0.6 | GHSA-9vhv-jxww-xfm5 | CVE-2026-112913 | 🟢 Baja (3.3) | 4.2.1 | ídem | **No.** Solo afecta a Windows y el worker corre en Linux. |
| `filelock` | 4.0.6 | GHSA-567q-5qvw-pf92 | CVE-2026-112907 | 🟢 Baja (2.5) | 4.2.1 | ídem | **No.** Solo afecta a Windows (oplock en `SoftFileLock`). |

**Acción recomendada (esfuerzo bajo):**

- **`undici`:** añadir un override en `apps/web/pnpm-workspace.yaml`, siguiendo la convención existente de mismo major.
  ```yaml
  overrides:
    undici@^7: ^7.30.1
  ```
  Mejor aún: mover `shadcn` a `devDependencies` (ver D-01), con lo que `undici` deja de llegar a la imagen de producción.
- **`filelock`:** subirlo a ≥ 4.2.1 con `uv lock --upgrade-package filelock`.

---

## 4. Hallazgos por área

Severidad: 🔴 Crítico · 🟠 Alto · 🟡 Medio · 🟢 Bajo. Un hallazgo marcado *Discutible* es una decisión defendible, no un error.

No hay hallazgos 🔴 confirmados: ninguno permite hoy comprometer cuentas ni datos sin precondiciones fuertes.

### 4.1 Arquitectura y estructura — 8/10

**🟡 A-01. El módulo `reports` importa directamente los modelos de `pipeline` y `sources`.**
- **Evidencia:** `apps/api/app/modules/reports/service.py:14,24` importa `Claim`, `Evidence` y `Source`. El docstring de `sources/reputation.py:3-9` declara la regla contraria: los módulos se hablan por la capa de servicio.
- **Por qué importa:** la regla de límites entre módulos se cumple solo a medias, así que un cambio de esquema en `pipeline` rompe `reports` sin pasar por un contrato.
- **Corrección:** exponer en `pipeline/service.py` una función `list_claims_with_evidence(submission_id)` que devuelva DTOs, y que `reports` consuma eso.

**🟢 A-02. Skills de agentes duplicadas en el repo.**
- **Evidencia:** `.agents/skills/` y `.claude/skills/` contienen los mismos 102 archivos `higgsfield-*`.
- **Por qué importa:** ruido en el repo y en las revisiones, y riesgo de que las dos copias diverjan.
- **Corrección:** dejar una sola copia (o un symlink) y gestionar la otra con `skills-lock.json`.

**🟢 A-03. `apps/web/lib/utils.ts:1` solo reexporta `cn`.**
- **Evidencia:** los componentes de `components/ui/*` importan `cn` directamente de `"cn"`, mientras que las páginas pasan por `@/lib/utils`.
- **Corrección:** elegir una sola vía de importación.

**✅ Bien hecho:**
- Separación `routers → service → models` consistente en cada módulo.
- `core/` concentra lo transversal: config, seguridad, middleware e IP del cliente.
- `models_registry.py` resuelve con un comentario claro el problema de metadatos en procesos que no importan todos los módulos.

### 4.2 Uso de frameworks — 7/10

**🟠 F-01. Las llamadas a Claude no contemplan el pensamiento adaptativo de Sonnet 5 ni las paradas propias de las herramientas de servidor.**
- **Evidencia:**
  - `apps/api/app/modules/pipeline/claims.py:57-63` usa `max_tokens=2048`.
  - `apps/api/app/modules/pipeline/verify.py:147-161` usa `max_tokens=4096` y no revisa `response.stop_reason`.
- **Qué está mal:**
  - Con `claude-sonnet-5`, omitir `thinking` deja el pensamiento adaptativo activo, y los tokens de pensamiento cuentan contra `max_tokens`. Con 2048/4096 es probable cortar en `max_tokens` antes del JSON final, sobre todo en `verify`, que además hace hasta 5 búsquedas.
  - Con `web_search`, el bucle del servidor puede devolver `stop_reason == "pause_turn"`. El código lo trata como «no devolvió texto», reintenta desde cero (gastando de nuevo) y termina en `INSUFFICIENT`.
  - Tampoco se maneja `stop_reason == "refusal"`.
- **Por qué importa:** casos marcados `INSUFFICIENT` o `failed` por truncado, no por falta de evidencia, y costo duplicado.
- **Corrección:**
  ```python
  response = await client.messages.create(
      model=model_name,
      max_tokens=16000,                     # margen para pensamiento + JSON
      output_config={"effort": "medium"},   # medir; tarea de extracción/verificación acotada
      ...
  )
  while response.stop_reason == "pause_turn":
      messages = [*messages, {"role": "assistant", "content": response.content}]
      response = await client.messages.create(..., messages=messages)
  if response.stop_reason in ("max_tokens", "refusal"):
      logger.warning("verify_claim_stopped", stop_reason=response.stop_reason)
      return _insufficient("No se pudo completar la verificación de esta afirmación.")
  ```

**🟡 F-02. La verificación parsea JSON a mano en vez de usar salidas estructuradas.**
- **Evidencia:** `verify.py:117-126,174-179` quita las vallas ```` ``` ```` y hace `json.loads`. En cambio, `claims.py` sí usa `messages.parse(output_format=...)`.
- **Corrección:** usar `client.messages.parse(..., output_format=_RawVerifyResult)` también en `verify`. La documentación del SDK lista Sonnet 5 entre los modelos con salidas estructuradas.
- *No verificado:* la compatibilidad de salidas estructuradas con `web_search_20260209` en la misma petición. Hay que probarla en staging antes de migrar.

**🟡 F-03. Toda la web son componentes cliente con `fetch` en `useEffect`.**
- **Evidencia:** `apps/web/app/history/page.tsx:1,53-63`, `app/reports/[id]/page.tsx:1,62-102`, `app/sources/page.tsx` y las demás páginas empiezan con `"use client"`.
- **Por qué importa:** *Discutible.* Es coherente con las cookies de la API en otro dominio (documentado en el README), pero renuncia a Server Components y streaming. Además obliga a repetir en cada página la lógica de «401 → /login» (`history/page.tsx:57`, `reports/[id]/page.tsx:86`).
- **Corrección mínima:** un hook `useApiQuery` que centralice la carga, el error y la redirección al recibir 401. Corrección de fondo: leer `/sources`, que es pública, en un Server Component.

**🟢 F-04. `docs`, `redoc` y `openapi` desactivados en producción; CORS sin `*`.**
- **Evidencia:** `apps/api/app/main.py:40-62`.
- **Valoración:** bien hecho.
- **Detalle menor:** `allow_methods` incluye `PATCH` y `DELETE`, que ninguna ruta usa. Quitarlos.

**✅ Bien hecho:**
- `Annotated[..., Depends()]` en todas las rutas.
- `lifespan` en lugar de los eventos obsoletos.
- `async_sessionmaker` con `expire_on_commit=False`.
- `proxy.ts`, la convención de Next 16, para la puerta de la UI y el proxy `/api`.
- `messages.parse(output_format=Model)`, el helper vigente del SDK 1.x.
- `web_search_20260209`, la variante correcta para Sonnet 5.
- Los errores de las herramientas de servidor se distinguen correctamente: `isinstance(result_content, list)` en `verify.py:109-110`.

### 4.3 Dependencias — 7/10

**🟠 D-01. `shadcn` (el CLI) está en `dependencies` y el Dockerfile copia todo `node_modules` a producción.**
- **Evidencia:**
  - `apps/web/package.json:30`. En el código solo se usa `@import "shadcn/tailwind.css"` (`app/globals.css:3`), que se resuelve en tiempo de build.
  - `apps/web/Dockerfile:23` (`COPY --from=builder /app/node_modules ./node_modules`).
- **Por qué importa:** arrastra a la imagen de runtime el SDK de MCP, `undici`, `@dotenvx/dotenvx`, `execa`, `systeminformation` y todos los avisos de la sección 3. La imagen engorda y aumenta la superficie de ataque.
- **Corrección:** mover `shadcn` a `devDependencies` y usar `output: "standalone"` (ver O-02).

**🟡 D-02. Versiones mayores atrasadas.**
- **Evidencia:** `uv tree --outdated` y `pnpm outdated` muestran:
  - `anthropic` 1.9.0 → 2.3.0
  - `redis` 5.3.1 → 8.1.0
  - `fastapi` 0.141.1 → 0.162.0
  - `react` 19.2.8 → 19.3.1
  - `typescript` 5.9.3 → 7.0.2
  - `eslint` 9 → 10
  - `@types/node` 20 → 26
- **Por qué importa:** `@types/node ^20` no coincide con el runtime Node 22 de Docker/CI, y el SDK de Anthropic está un major por detrás: las funciones nuevas y las correcciones llegan antes al 2.x.
- **Corrección:** actualizar por lotes con los tests como red. Para `anthropic`, leer antes el CHANGELOG del 2.x. Mientras tanto, alinear `@types/node` con `^22`.

**🟡 D-03. Rangos sin techo de major en `pyproject.toml`.**
- **Evidencia:** `apps/api/pyproject.toml:6-30` usa solo `>=`, por ejemplo `anthropic>=0.40.0` cuando el lock ya está en 1.9.0, que tiene cambios incompatibles con 0.x.
- **Por qué importa:** el lock protege, pero un `uv lock --upgrade` saltaría majors sin aviso.
- **Corrección:** acotar los paquetes críticos, por ejemplo `anthropic>=1.9,<2` y `redis>=5.3,<6`, y subir el techo a propósito.

**🟢 D-04. Dos librerías de animación CSS.**
- **Evidencia:** `animate.css` y `tw-animate-css` en `package.json:20,32`.
- *Discutible:* `tw-animate-css` lo exige shadcn y `animate.css` es una decisión del spec de motion, pero conviene revisar si ambas hacen falta.

**✅ Bien hecho:**
- `uv sync --frozen` y `pnpm install --frozen-lockfile` en Docker y CI.
- Overrides de seguridad documentados y acotados al mismo major (`pnpm-workspace.yaml:5-14`).
- Next y React fijados exactos.
- `onlyBuiltDependencies` restringe los scripts de instalación.

### 4.4 Calidad de código — 8/10

**🟡 Q-01. `except Exception` amplios que ocultan errores de programación.**
- **Evidencia:**
  - `apps/api/app/core/security.py:36-37`: `verify_password` devuelve `False` ante cualquier excepción, incluido un hash corrupto (`InvalidHashError`), sin registrarla.
  - `claims.py:66` reintenta también errores no recuperables, como 401 o 400 del proveedor. Encima de eso actúan los 2 reintentos propios del SDK, así que hasta 9 llamadas.
- **Corrección:**
  ```python
  from argon2.exceptions import InvalidHashError, VerificationError
  except (VerifyMismatchError, VerificationError):
      return False
  except InvalidHashError:
      logger.error("password_hash_corrupt")
      return False
  ```
  En el LLM, capturar `anthropic.RateLimitError` y `APIConnectionError`/`InternalServerError` para reintentar, y dejar que `BadRequestError`/`AuthenticationError` fallen a la primera.

**🟢 Q-02. Código muerto.**
- **Evidencia:**
  - `apps/api/app/modules/auth/service.py:143-151`: un `try/except RateLimitExceeded: raise` que no hace nada.
  - `service.py:89`: `_check_not_locked` es `async` sin ningún `await`.
- **Corrección:** quitar el `try` y hacer la función síncrona.

**🟢 Q-03. Detección de error por texto en el frontend.**
- **Evidencia:** `apps/web/app/login/2fa/page.tsx:52` usa `err.message.includes("token")`, que depende del texto en español de la API (`routers.py:105,110`).
- **Corrección:** distinguir por `status` (401 con token caducado frente a 401 por código inválido) o con un `code` estable en el cuerpo del error.

**🟢 Q-04. Límite de entrada incoherente.**
- **Evidencia:** `submissions/schemas.py:22` limita `raw_input` a 10 000 caracteres, mientras que `MAX_TEXT_INPUT_CHARS` vale 20 000 (`config.py:109`, `.env.example:79`) y la web usa 10 000 (`submit/page.tsx:17`).
- **Corrección:** una sola fuente de verdad, con el schema leyendo el ajuste.

**✅ Bien hecho:**
- Errores de dominio con nombre (`AccountLockedError`, `SubmissionQuotaError`) traducidos en el router.
- Comentarios que explican el porqué, no el qué; por ejemplo `client_ip.py` y `orchestrator.py:88-94`.
- `ruff check` y `ruff format --check` limpios (82 archivos).
- TypeScript en modo `strict`.

### 4.5 Seguridad — 7/10

**🟠 S-01. SSRF por redirecciones y DNS rebinding en la ingesta de URL y video.**
- **Evidencia:** `apps/api/app/modules/pipeline/url_safety.py:24-56` resuelve el host y valida la IP. Pero `ingest.py:33` llama luego a `trafilatura.fetch_url(url)`, que resuelve de nuevo y sigue redirecciones; lo mismo pasa con `yt_dlp` (`ingest.py:55,71`). Está reconocido en el docstring (`url_safety.py:32-36`) y en el README.
- **Por qué importa:** el worker vive en la red privada junto a Postgres y Redis. Un servidor malicioso puede responder 302 hacia una dirección interna, o devolver una IP pública al validar y una privada al descargar (rebinding). El contenido extraído vuelve al usuario dentro del reporte (`extracted_text`) y llega al LLM.
- **Corrección:** descargar con `httpx` sin redirecciones automáticas, revalidar cada salto y fijar la IP ya validada. Después, pasar el HTML a `trafilatura.extract()`.
  ```python
  async def fetch_public(url: str, max_hops: int = 5, max_bytes: int = 5_000_000) -> str:
      async with httpx.AsyncClient(follow_redirects=False, timeout=15) as client:
          for _ in range(max_hops):
              await asyncio.to_thread(assert_public_http_url, url)
              r = await client.get(url)
              if r.is_redirect:
                  url = str(r.next_request.url)
                  continue
              r.raise_for_status()
              return r.text[:max_bytes]
      raise UnsafeUrlError("Demasiadas redirecciones.")
  ```
  Para cerrar también el rebinding, usar un transporte que conecte a la IP ya validada. Otra opción es un proxy de salida (egress) que bloquee los rangos privados. En yt-dlp, la lista blanca de hosts ya reduce mucho el riesgo.

**🟡 S-02. La web no envía cabeceras de seguridad.**
- **Evidencia:** `apps/web/next.config.ts:5` (`const nextConfig: NextConfig = {}`). No hay `headers()` ni CSP, y `app/layout.tsx:30` inyecta un script inline.
- **Por qué importa:** la API sí envía cabeceras (`core/middleware.py:33-69`), pero las páginas no. Sin `frame-ancestors`/`X-Frame-Options`, la web, incluida `/settings/security`, se puede enmarcar (clickjacking). Sin CSP, un XSS futuro no tiene contención, y el token `mfa_pending` vive en `sessionStorage` (`lib/auth.ts:35-45`).
- **Corrección:** cabeceras estáticas en `next.config.ts`, y CSP con nonce en `proxy.ts` según `node_modules/next/dist/docs/01-app/02-guides/content-security-policy.md`, aplicando el nonce al script de motion.
  ```ts
  const nextConfig: NextConfig = {
    output: "standalone",
    async headers() {
      return [{
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        ],
      }];
    },
  };
  ```

**🟡 S-03. Contenedores como root, y la imagen de la API instala dependencias de desarrollo.**
- **Evidencia:**
  - `apps/api/Dockerfile:19,22` usa `uv sync --frozen` sin `--no-dev`, así que pytest, ruff y respx viajan a producción. No hay `USER`.
  - `apps/web/Dockerfile` tampoco tiene `USER` (la imagen `node` ya trae el usuario `node`).
- **Corrección:**
  ```dockerfile
  RUN uv sync --frozen --no-dev --no-install-project
  ...
  RUN useradd --create-home app && chown -R app /app
  USER app
  ```

**🟡 S-04. El token `mfa_pending` no es de un solo uso.**
- **Evidencia:** `auth/routers.py:99-115` solo valida firma, scope y expiración. El `jti` (`core/security.py:88`) no se registra.
- **Por qué importa:** quien robe el token (vive 5 minutos en `sessionStorage`) puede pedir sesiones adicionales mientras tenga códigos válidos. El impacto es bajo porque igual hace falta el TOTP.
- **Corrección:** guardar `jti` en Redis con `SET jti NX EX 300` al verificar, y rechazarlo si ya existe.

**🟢 S-05. Las sesiones de acceso no se revocan al desactivar 2FA ni al cerrar sesión.**
- **Evidencia:** `logout` (`routers.py:311-320`) revoca solo el refresh, y el access JWT sigue válido hasta 15 minutos. `disable_mfa` (`service.py:297-316`) no revoca las otras familias de refresh.
- *Discutible:* es el trade-off habitual de los JWT cortos.
- **Corrección:** al desactivar 2FA, revocar todas las familias de refresh del usuario salvo la actual.

**🟢 S-06. Comparación CSRF no constante.**
- **Evidencia:** `core/deps.py:46` (`csrf_token != x_csrf_token`).
- **Riesgo:** casi nulo, porque el atacante no puede leer la cookie.
- **Corrección:** `hmac.compare_digest`, por consistencia con `client_ip.py:59`.

**🟢 S-07. `/sources/{domain}` expone públicamente `claim_id` de casos privados.**
- **Evidencia:** `sources/routers.py:51-55`.
- **Por qué importa:** son UUIDs y `/reports` es solo del dueño, así que no filtran contenido. Aun así, revelan actividad de usuarios en un endpoint sin autenticación.
- **Corrección:** quitar `claim_id` de `SourceScoreEventResponse` o reemplazarlo por un hash.

**🟢 S-08. Enumeración de correos.**
- **Evidencia:** `register` responde 409 (`routers.py:139-140`) y el lockout responde 423 (`routers.py:159-160`). Está documentado en el README.
- *Discutible:* trade-off aceptado para un MVP.

**🟢 S-09. La URL de la evidencia no se valida por esquema antes de usarla en `href`.**
- **Evidencia:** `app/reports/[id]/page.tsx:366`. Hoy la URL solo puede venir de resultados reales de búsqueda en dominios de la lista blanca (`verify.py:183-187`), así que no es explotable.
- **Corrección (defensa en profundidad):** exigir `https?://` en `EvidenceItem`.

**✅ Bien hecho:**
- argon2id con hash ficticio para igualar tiempos (`security.py:21-49`).
- Refresh opaco hasheado con SHA-256 y revocación de familia al detectar reutilización (`service.py:346-359`).
- TOTP con protección contra replay (`totp.py:46-65`) y secreto pendiente separado del activo (`models.py:22-25`).
- Fernet para los secretos en reposo.
- Fail-fast en producción con secretos de desarrollo o débiles (`config.py:142-182`).
- IP del cliente no falsificable (`client_ip.py`).
- 500 genéricos con `request_id` (`middleware.py:82-92`).
- Redacción de secretos en los logs.
- Prompts con delimitadores frente a inyección.
- Citas validadas contra los resultados reales.

### 4.6 Base de datos y datos — 6/10

**🟠 B-01. Actualizaciones de reputación sin bloqueo: se pierden escrituras con workers concurrentes.**
- **Evidencia:** `apps/api/app/modules/sources/reputation.py:86,131-136` lee `Source` y luego hace `source.alpha += 1` / `source.beta += 1` / `cases_count += 1` en Python. arq ejecuta hasta 10 trabajos en paralelo por worker, y la misma fuente aparece en muchos casos.
- **Por qué importa:** dos casos que puntúan la misma fuente a la vez escriben el mismo valor base y se pierde una actualización. La reputación es el activo central del producto.
- **Corrección:** incrementos atómicos en SQL, o `SELECT ... FOR UPDATE`.
  ```python
  await db.execute(
      update(Source).where(Source.id == source.id).values(
          alpha=Source.alpha + (1 if outcome == "hit" else 0),
          beta=Source.beta + (0 if outcome == "hit" else 1),
          cases_count=Source.cases_count + 1,
          last_updated=_utcnow(),
      )
  )
  ```
  Alternativa: `select(Source).where(...).with_for_update()`. También convendría `INSERT ... ON CONFLICT DO NOTHING` sobre `uq_source_score_event` en lugar del `SELECT` previo (`reputation.py:120-127`), que tiene la misma carrera.

**🟡 B-02. Rotación de refresh y consumo de códigos de recuperación sin bloqueo.**
- **Evidencia:**
  - `auth/service.py:346-389`: el refresh se lee, se valida y se marca sin `FOR UPDATE`.
  - `service.py:263-273`: los códigos de recuperación también.
  - `service.py:95-99`: `failed_attempts += 1` es una lectura-modificación-escritura.
- **Por qué importa:** dos `/auth/refresh` simultáneos con el mismo token pueden emitir dos sesiones hijas. El frontend lo mitiga con `refreshInFlight` (`lib/api.ts:34-52`), pero un atacante con el token no. Un código de recuperación podría usarse dos veces en paralelo, y los fallos concurrentes pueden contarse de menos y retrasar el bloqueo.
- **Corrección:** `select(...).with_for_update()` sobre la fila de `RefreshToken` y de `MfaRecoveryCode`, o un `UPDATE ... WHERE revoked_at IS NULL RETURNING id` que solo gane una vez. Para el contador, `update(User).values(failed_attempts=User.failed_attempts + 1)`.

**🟡 B-03. Cuotas con verificar-y-luego-insertar, y un caso puede quedar huérfano si falla el encolado.**
- **Evidencia:** `submissions/service.py:52-76` cuenta y después inserta (`:92-99`). Además, `:99` hace `commit` y `:102` encola. Si Redis falla entre ambos pasos, el caso queda `queued` para siempre y cuenta como activo, bloqueando al usuario (`max_active_submissions_per_user=2`).
- **Corrección:**
  - Envolver el `enqueue` en `try` y, si falla, marcar el caso `failed` y responder 503.
  - Añadir un *reaper* periódico (cron de arq) que marque `failed` los casos que lleven `queued` o en un estado intermedio más de `PIPELINE_JOB_TIMEOUT_SECONDS`.
  - Para la cuota diaria, un `pg_advisory_xact_lock(hash(user_id))` en la transacción basta.

**🟡 B-04. Faltan índices compuestos para las consultas reales.**
- **Evidencia:** las consultas filtran por `(user_id, status)` y `(user_id, created_at)` (`submissions/service.py:52-68,119-125`), pero solo existe `ix_submissions_user_id` (`alembic/versions/a7129a228980_...py:52`). Igual con `source_score_events (source_id, created_at DESC)` (`sources/service.py:41-46`), que hoy se cubre parcialmente con el índice de `source_id`.
- **Corrección:** `op.create_index("ix_submissions_user_created", "submissions", ["user_id", sa.text("created_at DESC")])`, y lo mismo para `source_score_events`.

**🟡 B-05. Listado sin paginación.**
- **Evidencia:** `GET /submissions` devuelve todos los casos con `raw_input` completo, de hasta 10 000 caracteres cada uno (`submissions/service.py:119-125`, `routers.py:63-69`).
- **Corrección:** paginación por cursor sobre `created_at` y un `raw_input` truncado en el listado.

**🟢 B-06. Estados y veredictos como `String` libre sin restricción.**
- **Evidencia:** `submissions/models.py:24`, `pipeline/models.py:22,44`, `sources/models.py:44`. Pydantic valida al leer, pero la BD acepta cualquier valor.
- **Corrección:** `CheckConstraint("status IN (...)")` o `sa.Enum(..., native_enum=False)`.

**🟢 B-07. `evidence.source_id` sin `ondelete`.**
- **Evidencia:** `pipeline/models.py:35-36`. Borrar una fuente falla si tiene evidencia.
- *Discutible:* probablemente deseable; dejarlo explícito con `ondelete="RESTRICT"`.

**✅ Bien hecho:**
- Restricción única `(source_id, claim_id)` para la idempotencia del scoring.
- `TIMESTAMPTZ` en todas las fechas.
- UUIDs como clave primaria.
- Migraciones Alembic versionadas y ejecutadas antes del arranque (`railway.toml:8`).
- Se escapa `%` en la URL de Alembic (`alembic/env.py:19-20`).
- Reintentos de arq protegidos contra doble scoring (`orchestrator.py:104-115`).

### 4.7 Rendimiento — 6/10

**🟡 R-01. argon2 bloquea el event loop.**
- **Evidencia:** `hash_password` y `verify_password` son síncronas (`core/security.py:27-49`) y se llaman desde rutas `async` (`auth/service.py:128,158`). La verificación de un código de recuperación hace hasta 10 argon2 seguidos (`service.py:269-273`).
- **Por qué importa:** cada login congela todas las peticiones del proceso durante unos 50–100 ms; un `recovery_code` puede bloquearlas cerca de 1 s.
- **Corrección:** `await asyncio.to_thread(verify_password_or_dummy, password, hash)`, o `anyio.to_thread.run_sync`. Para los códigos de recuperación, guardar un prefijo identificador (por ejemplo los primeros 4 caracteres en claro) y verificar contra un solo hash.

**🟡 R-02. El modelo Whisper se recarga en cada caso de video.**
- **Evidencia:** `orchestrator.py:70` crea `FasterWhisperTranscriber()` por trabajo. La caché vive en la instancia (`transcribe.py:24-29`), así que nunca se reutiliza.
- **Corrección:** crear el transcriptor en `startup` del worker (`ctx["transcriber"]`) o como singleton con `lru_cache`.

**🟡 R-03. La sesión de BD se retiene durante todo el pipeline.**
- **Evidencia:** `orchestrator.py:98` abre la sesión y la mantiene mientras se esperan las llamadas al LLM y la descarga de video (minutos). El pool por defecto (5 + 10 de overflow) con `max_jobs` de arq en 10 puede agotar las conexiones.
- **Corrección:** abrir sesiones cortas por fase, o fijar `pool_size`/`max_overflow` y `WorkerSettings.max_jobs` de forma coherente.

**🟢 R-04. Consultas N+1 en el pipeline.**
- **Evidencia:** `orchestrator.py:147` llama a `get_source_by_domain` por cada evidencia y `reputation.py:120-127` hace un `SELECT` por cada fuente. Con 16 fuentes y 8 afirmaciones el impacto es pequeño.
- **Corrección:** cargar `{domain: Source}` una vez por caso.

**🟢 R-05. Descarga de video sin tope de tamaño cuando no se conoce la duración.**
- **Evidencia:** `ingest.py:81-82` solo corta si `duration` existe, y las opciones de `_download_audio` (`:64-70`) no tienen `max_filesize`.
- **Corrección:** rechazar si `duration is None` y añadir `"max_filesize": 200 * 1024 * 1024` y `"match_filter"`.

**🟢 R-06. Web.**
- **Evidencia:** la línea base de Lighthouse móvil en `/` es 91 de rendimiento, LCP 3,5 s y CLS 0,02 (ledger del plan de motion). El CSS de la portada pesaba 63 kB (12,8 kB gzip) antes de las animaciones.
- **Corrección:** revisar el LCP (fuentes Fontsource variables e imagen del hero), aunque la Tarea 7 del plan de motion ya lo mide.

**✅ Bien hecho:**
- Verificaciones en paralelo con `Semaphore` y timeout por afirmación (`orchestrator.py:39-60,128-131`).
- Trabajo bloqueante del pipeline en `asyncio.to_thread` (`ingest.py:41,78,90`).
- `Cache-Control: public, max-age=60` en `/sources` (`middleware.py:61-62`).
- `pool_pre_ping=True`.

### 4.8 Testing — 6/10

| Medición | Resultado |
|---|---|
| `pytest` (`apps/api`) | **141 passed, 1 skipped** en 33 s |
| Cobertura (`--cov=app`) | **84 %**. Bajas: `workers/arq_settings.py` 0 %, `pipeline/transcribe.py` 50 %, `core/queue.py` 58 %, `auth/routers.py` 60 %, `reports/service.py` 63 %, `submissions/service.py` 64 % |
| Tests web | `test:motion` (lógica pura de motion) y `test:scripts` (auditoría CSS). Ningún test de componentes, páginas ni flujos. |

Las coberturas de `auth/routers.py` y `reports/service.py` parecen bajas para lo que prueban `test_auth_flow.py` y `test_reports.py`. Es posible que coverage subcuente líneas tras `await` bajo `ASGITransport`. No lo verifiqué.

**🟠 T-01. Los tests corren sobre SQLite, no sobre Postgres.**
- **Evidencia:** `apps/api/tests/conftest.py:60-68` usa `sqlite+aiosqlite:///:memory:` y `Base.metadata.create_all`, no las migraciones. El único test de integración se salta salvo con `RUN_INTEGRATION_TESTS=1` (`conftest.py:18-21`).
- **Por qué importa:** no se prueban las migraciones reales, `TIMESTAMPTZ` (el código compensa con `_aware()`, `service.py:79-86`), los bloqueos ni la concurrencia. Ninguno de los hallazgos B-01 a B-03 puede salir en la suite actual.
- **Corrección:** un fixture con Postgres real (testcontainers o el servicio `postgres` de GitHub Actions) que ejecute `alembic upgrade head`, más tests de concurrencia con `asyncio.gather` sobre la reputación y el refresh.

**🟠 T-02. La web no tiene tests funcionales ni e2e.**
- **Evidencia:** solo existen `apps/web/lib/motion/motion.test.mjs` y `scripts/css-audit-lib.test.mjs`.
- **Por qué importa:** los flujos críticos de login, 2FA, refresh ante 401 (`lib/api.ts:65-96`, con lógica sutil de CSRF) y polling del reporte no tienen red de seguridad.
- **Corrección:** tests unitarios de `apiFetch` (Vitest + MSW) y un e2e con Playwright de registro → login → 2FA → envío → reporte contra el `docker compose`.

**🟡 T-03. `FakeRedis` no reproduce la expiración.**
- **Evidencia:** `conftest.py:24-47`. `ttl()` devuelve 60 por defecto y nunca expira, así que las ventanas del rate limit no se prueban de verdad.
- **Corrección:** usar `fakeredis[lua]` o el Redis del compose en la integración.

**✅ Bien hecho:**
- Tests de dominio de calidad: endurecimiento de MFA, IP del cliente (cabeceras falsificadas), configuración insegura, SSRF, validación de citas, reputación al 98 % e idempotencia del orquestador.
- `respx` para HTTP.
- `dependency_overrides` en lugar de parchear globales.

### 4.9 DevOps y configuración — 5/10

**🟠 O-01. La API no tiene CI, y no hay escaneo de dependencias automatizado.**
- **Evidencia:** solo existe `.github/workflows/web.yml`, filtrado por `apps/web/**`. Nada ejecuta `pytest`, `ruff` ni la construcción de las imágenes Docker. OSV-Scanner se ejecutó a mano (ver `VULNERABILIDADES.md`), y los dos avisos de la sección 3 aparecieron después sin que nada avisara.
- **Corrección:**
  ```yaml
  # .github/workflows/api.yml
  on:
    pull_request: { paths: ["apps/api/**", ".github/workflows/api.yml"] }
    push: { branches: [main], paths: ["apps/api/**"] }
  jobs:
    check:
      runs-on: ubuntu-latest
      services:
        postgres: { image: "postgres:16-alpine", env: { POSTGRES_PASSWORD: test }, ports: ["5432:5432"] }
        redis: { image: "redis:7-alpine", ports: ["6379:6379"] }
      defaults: { run: { working-directory: apps/api } }
      steps:
        - uses: actions/checkout@v4
        - uses: astral-sh/setup-uv@v6
        - run: uv sync --frozen
        - run: uv run ruff check . && uv run ruff format --check .
        - run: uv run pytest --cov=app
  ```
  Añadir también `google/osv-scanner-action` en un cron semanal y en cada PR, y Dependabot o Renovate.

**🟡 O-02. La imagen web no usa `output: "standalone"`.**
- **Evidencia:** `apps/web/Dockerfile:22-25` copia `node_modules` completo, incluidas las dependencias de desarrollo y el CLI de shadcn. `next.config.ts` no define `output`.
- **Corrección:** `output: "standalone"` y copiar `.next/standalone`, `.next/static` y `public`, según `node_modules/next/dist/docs/01-app/03-api-reference/05-config/01-next-config-js/output.md`. Arrancar con `node server.js` como `USER node`.

**🟡 O-03. Sin monitoreo, métricas ni alertas.**
- **Evidencia:**
  - Hay logging JSON con `request_id` (`core/logging.py`, `core/middleware.py`).
  - No hay errores agregados (Sentry o similar), métricas de la cola o del costo del LLM, ni alertas sobre casos `failed`.
  - El uso de tokens (`response.usage`) no se registra en `claims.py` ni en `verify.py`, así que el gasto no se puede auditar por caso.
- **Corrección:**
  - Registrar `usage` (input, output, búsquedas) por caso.
  - Integrar un servicio de errores.
  - Alertar sobre la tasa de `failed` y la antigüedad de la cola.

**🟡 O-04. El worker no tiene healthcheck.**
- **Evidencia:** `docker-compose.yml:52-65` y `apps/api/railway.worker.toml` no definen ningún healthcheck para el worker. Si arq se cuelga, nada lo reinicia.
- **Corrección:** arq publica su health en Redis (`health_check_key`); comprobarlo desde un healthcheck o desde el reaper de B-03.

**🟢 O-05. `docker-compose.yml` publica Postgres y Redis en el host con credenciales por defecto.**
- **Evidencia:** `docker-compose.yml:8-9,20-21`.
- *Discutible:* es un compose de desarrollo, pero conviene publicarlos en `127.0.0.1:5432:5432` para no exponerlos en la red local.

**🟢 O-06. Versiones de Node no declaradas, y acciones de GitHub fijadas por etiqueta y no por SHA.**
- **Evidencia:** no hay `engines` en `package.json`. Docker y CI usan Node 22 y el entorno local usa 24. `web.yml:28-33` usa `@v4`.
- **Corrección:** `"engines": { "node": ">=22 <23" }` y fijar las acciones por SHA.

**✅ Bien hecho:**
- Configuración tipada con pydantic-settings y validación al arrancar.
- `.env.example` documentado variable por variable.
- Migraciones en `preDeployCommand`.
- `healthcheckPath = "/health/ready"` con comprobación de BD y Redis.
- `exec` y `--no-proxy-headers` bien razonados en el `CMD` (`apps/api/Dockerfile:26-31`).
- CI de la web con `concurrency` y `permissions: contents: read`.

### 4.10 Documentación — 7/10

**🟡 DOC-01. `apps/web/README.md` es el de `create-next-app`.**
- **Evidencia:** `apps/web/README.md:1-36` menciona `npm`/`yarn`/`bun`, Geist y `next/font`, nada de lo cual se usa (el proyecto usa pnpm y Fontsource).
- **Corrección:** reemplazarlo por un README propio (scripts, variables `NEXT_PUBLIC_*`, `proxy.ts`, convenciones de motion) o borrarlo y enlazar al de la raíz.

**🟢 DOC-02. Falta un runbook de operación.**
- **Evidencia:** no hay documentación para rotar secretos (JWT, Fernet), reprocesar casos `failed` ni restaurar backups.
- **Corrección:** `docs/operations.md`.

**🟢 DOC-03. El README raíz dice «Next.js 16 (App Router, componentes cliente)».**
- **Evidencia:** está correcto, pero no explica por qué todo es cliente (las cookies de la API en otro dominio).
- **Corrección:** añadir una línea con el motivo, para que nadie lo «arregle» sin saberlo.

**✅ Bien hecho:**
- El README raíz es excepcional: arquitectura con diagrama, endpoints, flujo de un caso, despliegue en Railway y Vercel con el porqué de cada variable, y limitaciones conocidas honestas.
- `docs/reputation.md` documenta la fórmula y su circularidad.
- `docs/css-quality.md` y los specs y planes de `docs/superpowers/` completan la documentación.

---

## 5. Fortalezas del proyecto

1. **Autenticación de nivel profesional:**
   - argon2id con igualación de tiempos
   - refresh rotativo con revocación de familia
   - CSRF de doble envío
   - TOTP anti-replay con enrolamiento en dos fases
   - recuperación de un solo uso
   - IP del cliente no falsificable detrás de proxies
2. **Principio de producto aplicado por código, no solo por prompt.** Ninguna cita llega al reporte sin aparecer en los resultados reales de búsqueda y en la lista blanca. Un veredicto direccional sin una cita de la misma postura se degrada a `INSUFFICIENT` (`verify.py:181-214`).
3. **Fail-fast de configuración.** La API se niega a arrancar en producción con secretos de desarrollo, claves Fernet inválidas o CORS `*`.
4. **Errores que no filtran detalles internos:**
   - 500 genéricos con `request_id`
   - mensajes de pipeline seguros para el usuario (`orchestrator.py:20-27,175-181`)
   - redacción de secretos en los logs
5. **Robustez del worker.** Maneja la cancelación por timeout de arq (`CancelledError` + `shield`) y los reintentos tras una muerte del worker, sin duplicar el scoring.
6. **Disciplina de calidad:**
   - ruff limpio
   - TypeScript estricto
   - Stylelint y auditoría de CSS
   - lockfiles congelados
   - overrides de seguridad documentados
   - 141 tests con buenos casos negativos
7. **Documentación honesta** que reconoce las limitaciones (SSRF por redirecciones, circularidad de la reputación, enumeración por 423).

---

## 6. Plan de acción priorizado

### Quick wins (horas)

| # | Acción | Hallazgos | Esfuerzo |
|---|---|---|---|
| 1 | Subir `undici` (override `^7.30.1`) y `filelock` (≥ 4.2.1); mover `shadcn` a `devDependencies` | §3, D-01 | Bajo |
| 2 | `max_tokens` a ~16 000 y manejo de `pause_turn`, `max_tokens` y `refusal` en `claims.py`/`verify.py`; registrar `response.usage` | F-01, O-03 | Bajo |
| 3 | Cabeceras de seguridad estáticas en `next.config.ts` | S-02 | Bajo |
| 4 | `uv sync --no-dev` y `USER` no root en los dos Dockerfiles | S-03 | Bajo |
| 5 | argon2 en `asyncio.to_thread` | R-01 | Bajo |
| 6 | Transcriptor Whisper único por worker | R-02 | Bajo |
| 7 | Incremento atómico de `alpha`/`beta`/`cases_count` | B-01 | Bajo |
| 8 | Limpiezas: `try` muerto, `except` amplios de argon2, `compare_digest` en CSRF, `PATCH`/`DELETE` fuera de CORS, límite de `raw_input` unificado, `claim_id` fuera de `/sources/{domain}`, `apps/web/README.md` | Q-01–Q-04, S-06, S-07, F-04, DOC-01 | Bajo |

### Mediano plazo (días)

| # | Acción | Hallazgos | Esfuerzo |
|---|---|---|---|
| 9 | Workflow de CI para la API (ruff + pytest con Postgres y Redis de servicio) y OSV-Scanner programado con Dependabot o Renovate | O-01, T-01 | Medio |
| 10 | Bloqueos en el refresh, los códigos de recuperación y el contador de fallos; `jti` de un solo uso para `mfa_pending` | B-02, S-04 | Medio |
| 11 | Encolado con compensación y *reaper* de casos colgados; healthcheck del worker | B-03, O-04 | Medio |
| 12 | Descarga de URL propia con `httpx` (sin redirecciones automáticas, revalidación por salto, tope de tamaño) y luego `trafilatura.extract`; tope de tamaño en yt-dlp | S-01, R-05 | Medio |
| 13 | `output: "standalone"` en la imagen web | O-02 | Medio |
| 14 | Índices compuestos y paginación de `/submissions` | B-04, B-05 | Medio |
| 15 | Tests de `apiFetch` con Vitest + MSW, y un e2e con Playwright del flujo principal | T-02 | Medio |

### Largo plazo (semanas)

| # | Acción | Hallazgos | Esfuerzo |
|---|---|---|---|
| 16 | CSP con nonce vía `proxy.ts` (requiere renderizado dinámico) | S-02 | Medio-alto |
| 17 | Actualizar majors: `anthropic` 2.x (leer el CHANGELOG), redis-py, TypeScript 7, ESLint 10; acotar los rangos de `pyproject.toml` | D-02, D-03 | Alto |
| 18 | Migrar `verify` a salidas estructuradas, tras probar la compatibilidad con `web_search` en staging; evaluar `effort` por ruta | F-02 | Medio |
| 19 | Observabilidad completa: errores agregados, métricas de cola y costo, alertas, backups probados y runbook | O-03, DOC-02 | Alto |
| 20 | Contratos entre módulos (`reports` vía servicios de `pipeline`) y constraints de estado en la BD | A-01, B-06 | Medio |
| 21 | Evaluar Server Components para las páginas públicas (`/sources`) y un hook de datos común para las privadas | F-03 | Alto |

---

### Qué no pude verificar

- **Comportamiento en producción:** Railway y Vercel no se consultaron. `docs/AUDIT.md` cubre la revisión en vivo del 2026-10-07.
- **Llamadas reales a Claude:** no se ejecutaron. El análisis de F-01 se basa en el comportamiento documentado de Sonnet 5 (pensamiento adaptativo por defecto) y de las herramientas de servidor (`pause_turn`).
- **`allowed_callers: ["direct"]`** en la herramienta `web_search` (`verify.py:157`): no figura en la documentación de referencia consultada. Si la API lo acepta, presumiblemente desactiva el filtrado dinámico, como describe el README. Conviene confirmarlo con la documentación oficial.
- **Lint y build de la web:** no se ejecutaron durante la auditoría, porque la Tarea 5 estaba modificando esos archivos. El CI (`web.yml`) los ejecuta en cada PR.
- **Cobertura:** la de `auth/routers.py` y `reports/service.py` puede estar subestimada por la instrumentación bajo ASGI.

---

## 7. Estado del plan de acción (2026-10-24)

Comprobado contra el código de `main` el 2026-10-24. El análisis de seguridad posterior está en [SEGURIDAD.md](SEGURIDAD.md).

### Quick wins

| # | Acción | Estado |
|---|---|---|
| 1 | `undici`, `filelock` y `shadcn` en dev | ✅ PR #6 |
| 2 | `max_tokens`, `pause_turn`, `refusal` y `response.usage` | ✅ PR #6 |
| 3 | Cabeceras de seguridad en `next.config.ts` | ✅ PR #6. La CSP llegó en el PR #11. |
| 4 | `uv sync --no-dev` y usuario no root en los Dockerfiles | ✅ PR #6 (`USER app` y `USER node`) |
| 5 | argon2 en `asyncio.to_thread` | ✅ PR #6 |
| 6 | Un solo transcriptor Whisper por worker | ✅ PR #6 |
| 7 | Incremento atómico de `alpha`, `beta` y `cases_count` | ✅ PR #6 |
| 8 | Limpiezas (Q-01 a Q-04, S-06, S-07, F-04, DOC-01) | ✅ PR #6. Q-04 (límite de `raw_input`) se dejó a propósito, porque los dos límites miden cosas distintas. |

### Mediano plazo

| # | Acción | Estado |
|---|---|---|
| 9 | CI de la API, OSV-Scanner programado y Dependabot | 🟡 Parcial. Dependabot (npm, uv y Actions) está activo y sus lotes llegaron en los PR #24 y #32. **Pendiente:** el workflow de la API (`ruff` y `pytest`) y OSV programado. |
| 10 | Bloqueos en refresh, códigos de recuperación y contador; `jti` de un solo uso | 🟡 Parcial. El `jti` de un solo uso para `mfa_pending` está en el PR #34 (H-04). **Pendiente:** los bloqueos de fila (B-02). |
| 11 | Encolado con compensación, recolector de casos colgados y healthcheck del worker | ❌ Pendiente |
| 12 | Descarga de URL propia con `httpx` y tope de tamaño | 🟡 La descarga propia ya revalida cada salto y corta a 5 MB (`url_safety.py`, PR #11, H-01). **Pendiente:** tope de tamaño en yt-dlp. |
| 13 | `output: "standalone"` en la imagen web | ❌ Pendiente |
| 14 | Índices compuestos y paginación de `/submissions` | ❌ Pendiente |
| 15 | Tests de `apiFetch` (Vitest + MSW) y e2e con Playwright | ❌ Pendiente. La web solo tiene `node --test` para `lib/` (`test:motion`, `test:lib`). |

### Largo plazo

| # | Acción | Estado |
|---|---|---|
| 16 | CSP | 🟡 CSP estática en el PR #11 (`lib/csp.mjs`). Se descartó el nonce para no perder la caché de Vercel. |
| 17 | Actualizar majors | 🟡 Dependabot mantiene las menores. **Pendiente:** `anthropic` 2.x (`pyproject.toml` sigue en `>=0.40.0`), TypeScript 7, ESLint 10 y acotar los rangos. |
| 18 | Salidas estructuradas en `verify` | ❌ Pendiente |
| 19 | Observabilidad completa | 🟡 Eventos de seguridad `auth.*` y `ssrf.blocked` en el PR #11 (H-03). **Pendiente:** errores agregados, métricas, alertas, backups probados y runbook. |
| 20 | Contratos entre módulos y constraints de estado | ❌ Pendiente |
| 21 | Server Components para las páginas públicas | ❌ Pendiente. El PR #33 (Lighthouse móvil) midió que es lo que daría margen real de rendimiento en móvil. |

