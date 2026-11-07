// A source's date is free text. Whatever a browser can't read as a date goes
// apart, in the order it came: guessing would put it in the wrong place.
/**
 * @template {{ published_at: string | null }} T
 * @param {T[]} evidence
 * @returns {{ dated: T[], undated: T[] }}
 */
export function orderEvidence(evidence) {
  const timeOf = (item) => new Date(item.published_at ?? "").getTime();
  const undated = evidence.filter((item) => Number.isNaN(timeOf(item)));
  const dated = evidence
    .filter((item) => !Number.isNaN(timeOf(item)))
    .sort((a, b) => timeOf(a) - timeOf(b));
  return { dated, undated };
}
