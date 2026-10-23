import { gzipSync } from "node:zlib";
import { analyze } from "@projectwallace/css-analyzer";

/**
 * Resume un CSS con las métricas que nos interesan de Project Wallace.
 * Los campos `unique.*` son conteos de valores distintos.
 */
export function summarize(css) {
  const r = analyze(css);
  return {
    bytes: Buffer.byteLength(css),
    gzipBytes: gzipSync(css).length,
    rules: r.rules.total,
    selectors: r.selectors.total,
    declarations: r.declarations.total,
    specificity: {
      max: r.selectors.specificity.max,
      mean: r.selectors.specificity.mean,
    },
    maxSelectorComplexity: r.selectors.complexity.max,
    importants: r.declarations.importants.total,
    unique: {
      colors: r.values.colors.totalUnique,
      fontSizes: r.values.fontSizes.totalUnique,
      zIndexes: r.values.zindexes.totalUnique,
      durations: r.values.animations.durations.totalUnique,
      timingFunctions: r.values.animations.timingFunctions.totalUnique,
    },
  };
}

/** Rutas de las hojas de estilo `<link rel="stylesheet">` del HTML, sin query string. */
export function findPageStylesheets(html) {
  const paths = [];
  for (const [tag] of html.matchAll(/<link\b[^>]*>/gi)) {
    if (!/\brel=["']?stylesheet["']?/i.test(tag)) continue;
    const href = /\bhref=["']([^"']+)["']/i.exec(tag)?.[1];
    if (href) paths.push(href.split("?")[0]);
  }
  return paths;
}

const fmt = (n) => n.toLocaleString("es-ES");
const triple = (t) => `(${t.map((n) => Number(n.toFixed(2))).join(", ")})`;

export function formatSummary(title, s) {
  return [
    `== ${title} ==`,
    `Tamaño: ${fmt(s.bytes)} B (gzip: ${fmt(s.gzipBytes)} B)`,
    `Reglas: ${fmt(s.rules)}`,
    `Selectores: ${fmt(s.selectors)}`,
    `Declaraciones: ${fmt(s.declarations)}`,
    `Especificidad máxima: ${triple(s.specificity.max)}`,
    `Especificidad media: ${triple(s.specificity.mean)}`,
    `Complejidad máxima de selector: ${s.maxSelectorComplexity}`,
    `!important: ${fmt(s.importants)}`,
    `Colores únicos: ${s.unique.colors}`,
    `Tamaños de fuente únicos: ${s.unique.fontSizes}`,
    `z-index únicos: ${s.unique.zIndexes}`,
    `Duraciones de animación únicas: ${s.unique.durations}`,
    `Funciones de temporización únicas: ${s.unique.timingFunctions}`,
  ].join("\n");
}
