export const number = (v) =>
  v !== null && v !== undefined && v !== "" && Number.isFinite(Number(v))
    ? Number(v)
    : null;
export const fmt = (v, digits = 2) =>
  number(v) === null
    ? "—"
    : Number(v).toLocaleString("es-PE", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
export const signed = (v, digits = 2) =>
  `${number(v) > 0 ? "+" : ""}${fmt(v, digits)}`;
export function domain(values) {
  const finite = values.map(number).filter((v) => v !== null);
  if (!finite.length) return [0, 1];
  const [min, max] = finite.reduce(
    ([a, b], v) => [Math.min(a, v), Math.max(b, v)],
    [Infinity, -Infinity],
  );
  const p = Math.max((max - min) * 0.12, Math.abs(max) * 0.002, 0.000001);
  return [min - p, max + p];
}
export function gaps(rows, key, fields, maxGap) {
  return rows.flatMap((r, i) =>
    i && maxGap > 0 && r[key] - rows[i - 1][key] > maxGap
      ? [
          {
            [key]: (r[key] + rows[i - 1][key]) / 2,
            ...Object.fromEntries(fields.map((f) => [f, null])),
          },
          r,
        ]
      : [r],
  );
}
export function monthDays(data) {
  const count = new Date(Date.UTC(data.year, data.month, 0)).getUTCDate();
  const lookup = new Map(data.days.map((d) => [d.date, d]));
  return Array.from({ length: count }, (_, i) => {
    const date = `${data.year}-${String(data.month).padStart(2, "0")}-${String(i + 1).padStart(2, "0")}`;
    const r = lookup.get(date);
    return {
      ...r,
      date,
      day: i + 1,
      pnl: number(r?.net_pnl),
      trades: number(r?.trades),
    };
  });
}
