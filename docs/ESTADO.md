# Estado del proyecto — FakesNews

Última actualización: **2026-10-25**. Este documento sirve para retomar el trabajo en la próxima sesión: qué hay en `main`, qué se hizo en la última sesión y qué sigue pendiente, por orden de prioridad.

## Dónde está cada cosa

| | |
|---|---|
| Web (producción) | https://fakesnews.vercel.app (Vercel, despliega `main`) |
| API (producción) | https://fakesnews-production.up.railway.app (Railway, despliega `main`; la web la llama a través de `/api`) |
| Calidad | SonarQube Cloud, proyecto público `SantiagoTyrsArv_FAKESNEWS` (0 issues abiertos) |
| CI | `.github/workflows/web.yml` (lint, Stylelint, `tsc`, tests de `lib/` y build) + Dependabot (npm, uv y Actions) |
| Ramas | Solo `main`, en local y en remoto. Se trabaja en una rama por cambio con PR. |

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

1. **CI de la API:** un `.github/workflows/api.yml` con `ruff check`, `ruff format --check` y `pytest`, más OSV-Scanner programado. Es lo único que queda de SEGURIDAD.md (H-10) y protege todo lo demás.
2. **Robustez del backend** (AUDITORIA.md §7):
   - bloqueos de fila en refresh y en códigos de recuperación (B-02);
   - recolector de casos colgados y healthcheck del worker (B-03, O-04);
   - índices y paginación de `/submissions` (B-04, B-05);
   - tope de tamaño en yt-dlp;
   - `output: "standalone"` en la imagen web.
3. **Pruebas de la web** (en pausa hasta que el dueño lo indique): `apiFetch` con Vitest y MSW, y un e2e con Playwright del flujo principal.
4. **Largo plazo:**
   - subir el mínimo de `anthropic` en `pyproject.toml` a `>=2.1` (el lock ya tiene 2.1.0), TypeScript 7 y ESLint 10;
   - salidas estructuradas en `verify`;
   - observabilidad (alertas, métricas, backups probados);
   - Server Components para la portada y `/sources`.
5. **Detalles menores:**
   - el `import("lenis")` no tiene `.catch`;
   - pendientes de animación anotados en sesiones anteriores: SplitText antes de que carguen las fuentes, máscaras que recortan los descendentes y el cursor, que no se reclasifica al hacer scroll.

## Cómo se trabaja en este repositorio

- **Flujo:** especificación en `docs/superpowers/specs/`, luego plan en `docs/superpowers/plans/`, luego implementación, con la aprobación del dueño en cada paso. Un PR por cambio, con commits pequeños.
- **Fusión:** con merge commit, cuando el CI está en verde y Sonar no tiene issues nuevos.
- **Comprobaciones de la web** (`apps/web`): `pnpm lint`, `pnpm lint:css`, `pnpm exec tsc --noEmit`, `pnpm test:motion`, `pnpm test:lib` y `pnpm build`. Antes de usar APIs de Next 16, leer `node_modules/next/dist/docs/` (lo pide `apps/web/AGENTS.md`).
- **Comprobaciones de la API** (`apps/api`): `uv run python -m pytest -q`, `uv run ruff check .` y `uv run ruff format --check .`. En Windows, `uv run pytest` falla con «trampoline»; hay que usar `python -m pytest`.
- **Producción:** no se crean datos de prueba en producción (cuentas, casos). Los escaneos activos solo se hacen en local.
