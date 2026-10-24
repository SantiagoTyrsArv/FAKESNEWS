# Análisis de seguridad — FakesNews

- **Fecha:** 2026-10-24
- **Alcance:** la web en producción (`https://fakesnews.vercel.app`), la API en producción (`https://fakesnews-production.up.railway.app`), una copia local de ambas levantada con `docker compose` para los ataques, y el código de `main` (`bd1dc8e`).
- **Referencia:** OWASP Top 10:2025.

> **Estado al 2026-10-24 (tarde):** solo queda abierta la parte de H-10 que falta, el CI de la API. La [sección 8](#8-estado-al-2026-10-24-tarde) indica cómo y en qué PR se cerró cada hallazgo. El resto del documento describe el análisis tal como se hizo sobre `bd1dc8e`.

## 1. Resumen

El proyecto está en buen estado:
- **TLS:** las dos URLs públicas sacan **A+** en SSL Labs. Una de las dos IP de Vercel saca A (ver H-06).
- **Cabeceras:** la API saca **A+** en securityheaders.com y la web **A**.
- **Escaneo activo:** OWASP ZAP no encontró ninguna vulnerabilidad atacando la API con sesión iniciada (113 reglas: inyección SQL, XSS, path traversal, inyección de comandos, etc.).
- **Dependencias:** OSV-Scanner no encuentra ninguna vulnerabilidad conocida.

Lo más importante que queda por hacer:

1. **SSRF en la ingesta de URL** (H-01, OWASP A01). Es el único hallazgo con impacto real. Lo arrastra la auditoría anterior (S-01).
2. **La web no tiene Content-Security-Policy** (H-02, A02). Es lo único que le falta para el A+ y lo que señalan las tres herramientas.
3. **No hay registro de eventos de seguridad** (H-03, A09). Un ataque de fuerza bruta o una reutilización de token robado no dejaría rastro claro.

| Severidad | Hallazgos |
|---|---|
| 🟠 Media | 3 (H-01, H-02, H-03) |
| 🟢 Baja | 8 (H-04 a H-11) |

## 2. Herramientas y resultados

| Herramienta | Objetivo | Resultado |
|---|---|---|
| **securityheaders.com** | Web (producción) | **A**. Tiene HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy y Permissions-Policy. Le falta CSP y avisa de `Access-Control-Allow-Origin: *`. |
| **securityheaders.com** | API (producción) | **A+**. CSP `default-src 'none'; frame-ancestors 'none'`, COOP y CORP. |
| **SSL Labs** | API (Railway) | **A+**. TLS 1.2 y 1.3, certificado Let's Encrypt EC-256 (vence el 2026-12-26 y se renueva solo), HSTS de 1 año, forward secrecy, sin vulnerabilidades TLS conocidas. |
| **SSL Labs** | Web (Vercel) | **A+** en 216.198.79.67 y **A** en 64.29.17.67. TLS 1.2 y 1.3, certificado de Google Trust Services RSA-2048 (vence el 2026-11-27 y lo renueva Vercel), sin vulnerabilidades TLS. La IP con A no devolvió HSTS (H-06). |
| **OWASP ZAP, pasivo** (`zap-baseline`) | Web y API en producción | 0 fallos. Web: 2 avisos medios (sin CSP; CORS `*` en recursos estáticos) y 3 informativos. API: 1 informativo (Cache-Control). |
| **OWASP ZAP, activo** (`zap-api-scan` con sesión) | API local (OpenAPI) | **0 avisos, 0 fallos** y 113 reglas superadas. Las 51 respuestas 4xx son la API rechazando entradas inválidas, que es lo correcto. |
| **OWASP ZAP, activo** (`zap-full-scan`) | Web local | 0 fallos. 2 avisos: sin CSP (medio) y `X-Powered-By: Next.js` (bajo; solo en la imagen Docker, Vercel no lo envía). |
| **OSV-Scanner** 2.7 | `uv.lock` y `pnpm-lock.yaml` | **No issues found**: 98 paquetes Python y 725 npm. |
| **Revisión de código** | `main` | Comprobé el estado de S-01 a S-09 de [AUDITORIA.md](AUDITORIA.md) y revisé cada categoría del Top 10. |

El escaneo activo se hizo contra una copia local, no contra producción, para no dejar datos basura, no bloquear cuentas y no gastar créditos de Claude. El worker que procesa los envíos no se levantó.

## 3. Por categoría del OWASP Top 10:2025

| Categoría | Estado | Hallazgos |
|---|---|---|
| **A01 Broken Access Control** (incluye SSRF) | 🟠 | Control de acceso correcto: un caso ajeno responde igual que uno inexistente, sin IDOR. Queda el SSRF (H-01). |
| **A02 Security Misconfiguration** | 🟠 | Falta CSP (H-02). CORS `*` en estáticos (H-05), `X-Powered-By` (H-07). `/docs` y `/openapi.json` están apagados en producción ✅. |
| **A03 Software Supply Chain Failures** | 🟢 | Dependencias sin vulnerabilidades ✅. Actions fijadas a tags y sin Dependabot (H-10). |
| **A04 Cryptographic Failures** | ✅ | TLS A+, argon2id, refresh tokens hasheados, Fernet para secretos TOTP, JWT con algoritmo fijado. HSTS irregular en una IP de Vercel (H-06). |
| **A05 Injection** | ✅ | Solo ORM, sin SQL crudo. El único `dangerouslySetInnerHTML` es un script constante. ZAP: 0 en SQLi y XSS. URL de evidencia sin validar esquema (H-11). |
| **A06 Insecure Design** | ✅ | Tope de gasto de LLM por usuario, prompts delimitados frente a inyección y citas validadas contra resultados reales. |
| **A07 Authentication Failures** | 🟢 | Bloqueo de cuenta y rate limiting ✅, 2FA con protección contra replay ✅. Pendientes menores: H-04, H-08 y H-09. |
| **A08 Software or Data Integrity Failures** | ✅ | CI con `--frozen-lockfile`, cookies firmadas y CSRF de doble envío con comparación constante (S-06 corregido). |
| **A09 Security Logging and Alerting Failures** | 🟠 | Solo hay un log genérico por petición (H-03). |
| **A10 Mishandling of Exceptional Conditions** | ✅ | Los 500 son genéricos y llevan `request_id`; los errores no filtran detalles internos. |

## 4. Hallazgos

### 🟠 H-01. SSRF por redirecciones y DNS rebinding en la ingesta (A01) — antes S-01, sigue abierto

- **Dónde:** `apps/api/app/modules/pipeline/ingest.py:32-33`. `assert_public_http_url(url)` valida la IP, y después `trafilatura.fetch_url(url)` vuelve a resolver el dominio y sigue redirecciones. Pasa lo mismo con yt-dlp (`ingest.py:53,63`).
- **Riesgo:** el worker comparte red privada con Postgres y Redis. Un servidor malicioso puede responder con un 302 a una dirección interna, o devolver una IP pública al validar y una privada al descargar. El texto descargado vuelve al usuario en el reporte.
- **Corrección:** descargar con `httpx` sin seguir redirecciones, revalidar cada salto y conectar a la IP ya validada. Después, pasar el HTML a `trafilatura.extract()`. [AUDITORIA.md](AUDITORIA.md) §4.5 tiene el código propuesto.

### 🟠 H-02. La web no envía Content-Security-Policy (A02)

- **Evidencia:** securityheaders.com, ZAP pasivo (producción) y ZAP activo (local). La configuración está en `apps/web/next.config.ts`, que lo deja anotado: "No CSP yet".
- **Riesgo:** si algún día aparece un XSS, nada lo contiene, y el token `mfa_pending` vive en `sessionStorage`.
- **Corrección:** CSP con nonce por petición en `apps/web/proxy.ts`, según la guía de Next en `node_modules/next/dist/docs/01-app/02-guides/content-security-policy.md`. Hay que pasar el nonce al script inline de `app/layout.tsx`. Un punto de partida: `default-src 'self'; script-src 'self' 'nonce-…' 'strict-dynamic'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' <API>; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`. Conviene empezar con `Content-Security-Policy-Report-Only` y pasar a modo estricto cuando no haya violaciones.

### 🟠 H-03. Sin eventos de seguridad en los logs (A09)

- **Evidencia:** el módulo `apps/api/app/modules/auth` no registra nada. Solo `core/middleware.py` deja una línea por petición (método, ruta, estado).
- **Riesgo:** una fuerza bruta, un bloqueo de cuenta, la reutilización de un refresh token robado (que ya se detecta y revoca la familia) o la desactivación del 2FA quedan como un 401 o un 200 cualquiera. No se pueden investigar ni generar alertas.
- **Corrección:** eventos estructurados con structlog, sin datos sensibles (ni contraseñas ni tokens; el correo hasheado o el `user_id`):
  - `auth.login_failed`
  - `auth.lockout`
  - `auth.refresh_reuse_detected`
  - `auth.mfa_enabled` / `auth.mfa_disabled`
  - `auth.password_policy_rejected`
  - `ssrf.blocked`
  
  Después, una alerta en Railway sobre `auth.refresh_reuse_detected` y sobre picos de `auth.lockout`.

### 🟢 H-04. El token `mfa_pending` se puede usar más de una vez (A07) — antes S-04, sigue abierto

`core/security.py:93` genera un `jti`, pero nunca se registra. La corrección es guardar `SET jti NX EX 300` en Redis al verificarlo y rechazarlo si ya existe.

### 🟢 H-05. `Access-Control-Allow-Origin: *` en la web (A02)

Lo añade Vercel a las páginas prerenderizadas y a los estáticos. Como no hay cookies ni datos privados en esas respuestas, el riesgo es casi nulo, pero las herramientas lo marcan. Si se quiere quitar, se puede sobrescribir la cabecera en `next.config.ts` con el origen propio.

### 🟢 H-06. HSTS irregular en una IP de Vercel y sin `preload` (A04)

SSL Labs no recibió HSTS en 64.29.17.67, mientras que la otra IP sí lo devuelve. Conviene repetir el análisis: si persiste, el problema es de Vercel; si no, fue una respuesta de caché. Opcional: añadir `preload` cuando haya un dominio propio.

### 🟢 H-07. `X-Powered-By: Next.js` en la imagen Docker (A02)

Revela la tecnología del servidor. Se corrige con `poweredByHeader: false` en `next.config.ts`.

### 🟢 H-08. Las sesiones no se revocan al desactivar el 2FA (A07) — antes S-05, sigue abierto

Al desactivar el 2FA, conviene revocar todas las familias de refresh del usuario salvo la actual.

### 🟢 H-09. Política de contraseñas sin lista de contraseñas filtradas (A07)

Hoy se exigen 10 caracteres con mayúscula, minúscula y número (`core/security.py:55-69`). NIST 800-63B y OWASP ASVS recomiendan comprobar contraseñas filtradas (k-anonimato de Have I Been Pwned) en lugar de reglas de composición. La enumeración de correos (S-08) sigue aceptada como trade-off del MVP.

### 🟢 H-10. Cadena de suministro del CI (A03)

- Las Actions van fijadas a tags (`actions/checkout@v4`, `pnpm/action-setup@v4`, `actions/setup-node@v4`) y no a un SHA.
- No hay Dependabot.
- Solo hay CI para la web: la API no tiene workflow de tests ni de lint.

Lo recomendable es fijar las Actions a un SHA, añadir `.github/dependabot.yml` (npm, uv y github-actions) y un `api.yml` con `ruff`, `pytest` y `osv-scanner`.

### 🟢 H-11. La URL de la evidencia no se valida por esquema (A05) — antes S-09, sigue abierto

`verify.py:63` (`url: str`). Hoy no es explotable, porque las URL salen de búsquedas en dominios de la lista blanca. Como defensa en profundidad, conviene exigir `https?://` en `EvidenceItem`.

## 5. Corregido desde la auditoría del 2026-10-23

- **S-02 (cabeceras de la web):** corregido en parte; está todo salvo la CSP (H-02).
- **S-03 (contenedores como root y dependencias de desarrollo):** corregido; las dos imágenes tienen `USER`.
- **S-06 (comparación CSRF):** corregido; ahora usa `hmac.compare_digest`.
- **S-07 (`claim_id` público):** corregido.
- **Dependencias:** siguen limpias.

## 6. Plan sugerido

| Orden | Qué | Esfuerzo |
|---|---|---|
| 1 | H-01 SSRF: descarga con `httpx`, revalidación por salto y conexión a la IP validada | ~1 día |
| 2 | H-02 CSP con nonce (primero Report-Only), más H-07 `poweredByHeader: false` | ~medio día |
| 3 | H-03 eventos de seguridad y alerta en Railway | ~medio día |
| 4 | H-04 `jti` de un solo uso, H-08 revocar sesiones al desactivar el 2FA | ~2 h |
| 5 | H-10 Dependabot, Actions fijadas a SHA y CI de la API | ~2 h |
| 6 | H-09, H-11, H-05, H-06 | ~2 h |

## 7. Límites de este análisis

- **Producción:** solo recibió escaneos pasivos. El activo se hizo contra una copia local construida desde `main`, que puede diferir en variables de entorno.
- **Sesión en el escaneo de la API:** se usó la de un usuario de prueba local. El access token dura 15 minutos, así que la última parte del escaneo pudo correr sin sesión.
- **Fuera del escaneo:** el pipeline con Claude y el worker no se ejecutaron. La inyección de prompts y el SSRF se evaluaron leyendo el código.
- **Lógica de negocio:** ZAP no prueba lógica de negocio compleja, como condiciones de carrera en el tope de gasto o el flujo completo del 2FA.

## 8. Estado al 2026-10-24 (tarde)

| Hallazgo | Estado |
|---|---|
| H-01, H-02, H-03, H-07 | ✅ Corregidos en el PR #11. H-02 se resolvió con una CSP estática (`lib/csp.mjs`), no con nonce, para conservar la caché de Vercel. |
| H-04 | ✅ PR #34. El token `mfa_pending` solo vale una vez: su `jti` se registra en Redis al verificar con éxito, y un código mal tecleado no lo gasta. |
| H-05 | Aceptado: Vercel pone `*` en respuestas sin cookies ni datos privados. |
| H-06 | ✅ Las dos IP de Vercel devuelven `max-age=31536000; includeSubDomains` (3 de 3 peticiones cada una). `preload` queda pendiente hasta tener dominio propio. |
| H-08 | ✅ PR #34. Al desactivar el 2FA se revocan las demás sesiones (familias de refresh) y se mantiene la actual. |
| H-09 | ✅ PR #34. Lista local con las 5.791 contraseñas de la lista NCSC top 100k que cumplirían las reglas. No hay llamadas externas. |
| H-10 | Parcial: Actions fijadas a SHA y Dependabot configurado. Falta el CI de la API. |
| H-11 | ✅ PR #34. Solo las URL http(s) se convierten en enlace: se filtran en el pipeline, se validan en `EvidenceItem` y se comprueban en la web. |
