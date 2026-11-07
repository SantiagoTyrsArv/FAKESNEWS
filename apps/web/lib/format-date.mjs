// Sources give dates in several formats, and some aren't dates at all
// ("hace 2 días"): those stay as they are. UTC keeps the day the source wrote.
export function formatPublishedDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("es-CO", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}
