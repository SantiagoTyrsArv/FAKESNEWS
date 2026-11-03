# Estado del proyecto — FakesNews

Última actualización: **2026-11-03**. Este documento sirve para retomar el trabajo en la próxima sesión: qué hay en `main`, qué se hizo en la última sesión y qué sigue pendiente, por orden de prioridad.

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
| #39 | `docs/status-2026-10-25` | Registro de la sesión del 2026-10-25 |
| #40–#49 | Dependabot | API: pydantic-settings, fastapi 0.162, alembic, ruff, pytest 9.2. Web: next y eslint-config-next 16.4.3, shadcn 4.23, css-analyzer, lucide-react 1.66 |
| #50 | `feat/colombian-sources` | 9 fuentes colombianas de confianza |
| #51 | `fix/subdomain-evidence` | Las evidencias de subdominios de una fuente de confianza ya no se descartan |
| #52 | `feat/verdict-eval` | Evaluación de la calidad de los veredictos (`apps/api/evals/verdicts/`) |
| #53 | `fix/unsearchable-domains` | **No se mandan a la búsqueda los 8 medios que bloquean a Anthropic** (la verificación nunca había funcionado en producción) |

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

0. **Evaluación de veredictos (en curso):** correr los 4 casos restantes (`co-falso-2`, `co-verdadero-2`, `co-mixto-1` y `co-mixto-2`), unos 0,35 USD, **solo con la aprobación del dueño**. Después, con datos, decidir si se abarata producción: `effort: medium` en `verify`, búsquedas máximas de 5 a 3 y afirmaciones por envío de 8 a 4. Cada cambio va aparte y se mide con la evaluación. Mejoras menores pendientes de la evaluación: si se interrumpe con Ctrl+C se pierden los resultados, y `--dry-run` no avisa cuando el máximo estimado pasa el tope.
1. **CI de la API:** un `.github/workflows/api.yml` con `ruff check`, `ruff format --check` y `pytest`, más OSV-Scanner programado. Es lo único que queda de SEGURIDAD.md (H-10) y protege todo lo demás.
2. **Robustez del backend** (AUDITORIA.md §7):
   - bloqueos de fila en refresh y en códigos de recuperación (B-02);
   - recolector de casos colgados y healthcheck del worker (B-03, O-04);
   - índices y paginación de `/submissions` (B-04, B-05);
   - tope de tamaño en yt-dlp;
   - `output: "standalone"` en la imagen web.
3. **Pruebas de la web:** `apiFetch` con Vitest y MSW, y un e2e con Playwright del flujo principal. Ya hay créditos, pero el dueño eligió primero la evaluación de veredictos. Un e2e completo gasta ~0,70 USD por envío.
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
