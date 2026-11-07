# Estado del proyecto — FakesNews

Última actualización: **2026-11-07**. Este documento sirve para retomar el trabajo en la próxima sesión: qué hay en `main`, qué se hizo en la última sesión y qué sigue pendiente, por orden de prioridad.

## Dónde está cada cosa

| | |
|---|---|
| Web (producción) | https://fakesnews.vercel.app (Vercel, despliega `main`) |
| API (producción) | Azure Container Apps, `ca-fakesnews-api` en `rg-fakesnews-prod` (`northcentralus`). Despliega `main` con `api-deploy.yml` y la web la llama a través de `/api`. Runbook: [AZURE.md](AZURE.md) |
| Datos | PostgreSQL Flexible 18 privado (`psql-fakesnews`) y Redis interno (`ca-fakesnews-redis`). Secretos en Key Vault (`kv-fakesnews-4q4yxz5r`) |
| Calidad | SonarQube Cloud, proyecto público `SantiagoTyrsArv_FAKESNEWS` (0 issues abiertos y gate en verde en `main`, comprobado el 2026-11-06) |
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

## Para retomar (2026-11-07)

Producción funciona sobre Azure. Lo primero en la próxima sesión:

0. **Migrar la verificación a Tavily + Gemini:** los créditos de Anthropic se agotaron. Especificación y plan aprobados en `superpowers/`. La fase 0 dio 7 de 8 con `gemini-3.5-flash-lite` y `advanced` en el plan gratuito. Las claves están en el `.env` local; el proyecto de Gemini no debe tener facturación.
1. **Decidir la protección de `main`** ([SEGURIDAD.md §9](SEGURIDAD.md#9-revisión-de-dependencias-y-github-del-2026-11-06)): sigue sin configurar. Conviene exigir `check` y SonarCloud, y hacer que `api-deploy` dependa de las pruebas, porque hoy corren en paralelo.
2. **Decidir el modelo de producción:** corre `claude-sonnet-5`, mientras que toda la evaluación se hizo con `claude-sonnet-5-5`. Los 5 aciertos de 6 no dicen cómo se comporta el modelo de producción. O se cambia en `infra/main.bicepparam`, o se repite la evaluación con el modelo de producción. Ver la sesión del 2026-11-07, «Veredictos perdidos».
3. **Comprobar que Railway desapareció** después del 2026-11-09 02:25 UTC, cuando termina su purga (ver la sesión del 2026-11-07). Ya no hace falta `railway down` tras cada merge.
4. **Decidir sobre `co-mixto-1`:** la app dio `SUPPORTED` a una afirmación «Cuestionable», y no tiene un veredicto para lo que es cierto solo en parte. La evaluación de 6 casos ya está completa.
5. **Comprobar `railway.dump`** en el recurso compartido `pgdump`: debería tener los datos de la migración, pero el 2026-11-07 la cuenta de almacenamiento rechazó el acceso. Si sigue ahí, decidir si se conserva.
6. **Registro detallado de la migración:** `.superpowers/sdd/2026-11-04-azure-migration/progress.md`, sin versionar. Tiene cada decisión (`Ruling:`) y las mejoras menores aplazadas:
   - la app usa el usuario administrador de Postgres;
   - si Redis se reinicia, se pierde la cola (B-03);
   - `docker-compose.yml` sigue con Postgres 16;
   - los scripts pasan secretos como argumento de `az` en local.

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

0. ~~**Retirar Railway**~~ Hecho el 2026-11-07. Falta confirmar la purga después del 2026-11-09.
1. **Evaluación de veredictos (en curso):** correr los 4 casos restantes (`co-falso-2`, `co-verdadero-2`, `co-mixto-1` y `co-mixto-2`), unos 0,35 USD, **solo con la aprobación del dueño**. Después, con datos, decidir si se abarata producción: `effort: medium` en `verify`, búsquedas máximas de 5 a 3 y afirmaciones por envío de 8 a 4. Cada cambio va aparte y se mide con la evaluación. Mejoras menores pendientes de la evaluación: si se interrumpe con Ctrl+C se pierden los resultados, y `--dry-run` no avisa cuando el máximo estimado pasa el tope.
2. ~~**CI de la API**~~ Hecho en el #76. Falta que `api-deploy` dependa de las pruebas.
3. **Robustez del backend** (AUDITORIA.md §7):
   - bloqueos de fila en refresh y en códigos de recuperación (B-02);
   - recolector de casos colgados y healthcheck del worker (B-03, O-04);
   - índices y paginación de `/submissions` (B-04, B-05);
   - tope de tamaño en yt-dlp;
   - `output: "standalone"` en la imagen web.
4. **Pruebas de la web:** `apiFetch` con Vitest y MSW, y un e2e con Playwright del flujo principal. Ya hay créditos, pero el dueño eligió primero la evaluación de veredictos. Un e2e completo gasta ~0,70 USD por envío.
5. **Largo plazo:**
   - subir el mínimo de `anthropic` en `pyproject.toml` a `>=2.1` (el lock ya tiene 2.1.0), TypeScript 7 y ESLint 10;
   - salidas estructuradas en `verify`;
   - observabilidad (alertas, métricas, backups probados);
   - Server Components para la portada y `/sources`.
6. **Detalles menores:**
   - el `import("lenis")` no tiene `.catch`;
   - pendientes de animación anotados en sesiones anteriores: SplitText antes de que carguen las fuentes, máscaras que recortan los descendentes y el cursor, que no se reclasifica al hacer scroll.

## Cómo se trabaja en este repositorio

- **Flujo:** especificación en `docs/superpowers/specs/`, luego plan en `docs/superpowers/plans/`, luego implementación, con la aprobación del dueño en cada paso. Un PR por cambio, con commits pequeños.
- **Fusión:** con merge commit, cuando el CI está en verde y Sonar no tiene issues nuevos.
- **Comprobaciones de la web** (`apps/web`): `pnpm lint`, `pnpm lint:css`, `pnpm exec tsc --noEmit`, `pnpm test:motion`, `pnpm test:lib` y `pnpm build`. Antes de usar APIs de Next 16, leer `node_modules/next/dist/docs/` (lo pide `apps/web/AGENTS.md`).
- **Comprobaciones de la API** (`apps/api`): `uv run python -m pytest -q`, `uv run ruff check .` y `uv run ruff format --check .`. En Windows, `uv run pytest` falla con «trampoline»; hay que usar `python -m pytest`.
- **Producción:** no se crean datos de prueba en producción (cuentas, casos). Los escaneos activos solo se hacen en local.
