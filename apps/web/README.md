# FakesNews — web

Interfaz de FakesNews en Next.js 16 (App Router). La arquitectura, el despliegue y las variables
de entorno de todo el proyecto están en el [README de la raíz](../../README.md).

## Desarrollo

```bash
pnpm install
pnpm dev          # http://localhost:3000, contra la API en NEXT_PUBLIC_API_URL
```

| Script | Qué hace |
| --- | --- |
| `pnpm lint` | ESLint (`eslint-config-next`) |
| `pnpm lint:css` / `pnpm lint:css:fix` | Stylelint sobre los CSS |
| `pnpm css:audit` | Métricas del CSS compilado (ver `docs/css-quality.md`) |
| `pnpm test:scripts` | Tests de los scripts de `scripts/` (`node --test`) |
| `pnpm build` / `pnpm start` | Build y servidor de producción |

## Notas

- Las páginas son componentes cliente que llaman a la API desde el navegador: la sesión vive en
  cookies httpOnly de la API, que el servidor de Next no ve cuando web y API están en dominios
  distintos.
- `proxy.ts` solo redirige a `/login` cuando falta la cookie de sesión y, si `API_PROXY_TARGET`
  está definido, hace de proxy de la API en `/api`. La autorización real la hace siempre la API.
- `NEXT_PUBLIC_API_URL` se lee al compilar: cambiarla exige volver a hacer el build.
- Las cabeceras de seguridad de las páginas se definen en `next.config.ts`.
