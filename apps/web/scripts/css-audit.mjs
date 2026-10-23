// Auditoría de CSS con Project Wallace. Uso: pnpm css:audit [--json <archivo>]
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { findPageStylesheets, formatSummary, summarize } from "./css-audit-lib.mjs";

const NEXT_DIR = resolve(".next");
const STATIC_DIR = join(NEXT_DIR, "static");
const HOME_HTML = join(NEXT_DIR, "server", "app", "index.html");

if (!existsSync(STATIC_DIR)) {
  console.error('No hay build. Ejecuta "pnpm build" antes de "pnpm css:audit".');
  process.exit(1);
}

const jsonFlag = process.argv.indexOf("--json");
const jsonFile = jsonFlag === -1 ? null : process.argv[jsonFlag + 1];
if (jsonFlag !== -1 && !jsonFile) {
  console.error("Falta el archivo de salida: --json <archivo>");
  process.exit(1);
}

function listCss(dir) {
  return readdirSync(dir, { withFileTypes: true, recursive: true })
    .filter((e) => e.isFile() && e.name.endsWith(".css"))
    .map((e) => join(e.parentPath, e.name));
}

const readAll = (files) => files.map((f) => readFileSync(f, "utf8")).join("\n");

const build = summarize(readAll(listCss(STATIC_DIR)));
console.log(formatSummary("Todo el build", build));

let home = null;
if (existsSync(HOME_HTML)) {
  const paths = findPageStylesheets(readFileSync(HOME_HTML, "utf8")).map((href) =>
    join(NEXT_DIR, href.replace(/^\/_next\//, "")),
  );
  const files = paths.filter((f) => existsSync(f));
  const missing = paths.filter((f) => !existsSync(f));
  if (missing.length > 0) {
    console.error(`\nAviso: faltan hojas de estilo de la portada en disco: ${missing.join(", ")}`);
  }
  if (files.length > 0) {
    home = summarize(readAll(files));
    console.log(`\n${formatSummary("Portada (/)", home)}`);
  } else {
    console.error('Aviso: no se encontró ninguna hoja de estilo de la portada; se omite el bloque "Portada (/)".');
  }
} else {
  console.warn(`\nAviso: no existe ${HOME_HTML}; se omite el bloque "Portada (/)".`);
}

if (jsonFile) {
  writeFileSync(jsonFile, `${JSON.stringify({ build, home }, null, 2)}\n`);
  console.log(`\nResumen JSON escrito en ${jsonFile}`);
}
