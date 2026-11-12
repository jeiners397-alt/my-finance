export { number, fmt, signed, domain, gaps } from "../lib/data";
export const C = {
  green: "#39bd52",
  red: "#fa504b",
  blue: "#69aafa",
  muted: "#9299a5",
  grid: "#252d38",
};
export const axis = {
  tick: { fill: C.muted, fontSize: 12 },
  tickLine: false,
  axisLine: { stroke: C.grid },
};
export const tip = {
  background: "#111820",
  border: "1px solid #334155",
  borderRadius: 10,
  color: "#e5e7eb",
};
export function Panel({ title, subtitle, children }) {
  return (
    <section className="min-w-0 rounded-2xl border border-slate-800 bg-[#0d131c] p-4 shadow-lg sm:p-6">
      <header className="mb-5">
        <h2 className="text-lg font-bold tracking-wide sm:text-xl">{title}</h2>
        {subtitle && (
          <p className="mt-2 text-xs leading-5 text-slate-400">{subtitle}</p>
        )}
      </header>
      {children}
    </section>
  );
}
export function Empty({ message = "Sin datos para este periodo" }) {
  return (
    <div className="flex h-40 items-center justify-center text-sm text-slate-500">
      {message}
    </div>
  );
}
