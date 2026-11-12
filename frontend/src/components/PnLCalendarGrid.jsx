import { CalendarDays } from "lucide-react";
import { Panel, fmt, signed } from "./chartUtils";
import { monthDays } from "../lib/data";
export default function PnLCalendarGrid({ data, summary }) {
  if (!data) return null;
  const days = monthDays(data),
    s = summary ?? data.summary ?? {};
  const offset =
    (new Date(Date.UTC(data.year, data.month - 1, 1)).getUTCDay() + 6) % 7;
  const known = days.filter((d) => d.pnl !== null),
    active = known.filter(
      (d) => d.ledger_entries > 0 || d.trades > 0 || d.pnl !== 0,
    );
  const max = known.reduce((m, d) => Math.max(m, Math.abs(d.pnl)), 0.000001);
  const best = active.reduce((a, d) => (!a || d.pnl > a.pnl ? d : a), null),
    worst = active.reduce((a, d) => (!a || d.pnl < a.pnl ? d : a), null);
  const title = new Intl.DateTimeFormat("es-PE", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(Date.UTC(data.year, data.month - 1, 1));
  const info = [
    ["Días positivos", known.filter((d) => d.pnl > 0).length],
    ["Días negativos", known.filter((d) => d.pnl < 0).length],
    [
      "Sin cierres",
      known.every((d) => d.trades !== null)
        ? known.filter((d) => d.trades === 0).length
        : "—",
    ],
    ["Operaciones cerradas", fmt(s.trades, 0)],
    ["Mejor día", best ? `${best.day} (${signed(best.pnl)})` : "—"],
    ["Peor día", worst ? `${worst.day} (${signed(worst.pnl)})` : "—"],
    ["Comisiones", `${fmt(s.commissions, 3)} ${data.currency}`],
  ];
  return (
    <Panel
      title={
        <span className="flex items-center gap-3 capitalize">
          <CalendarDays size={20} />
          {title}
        </span>
      }
      subtitle={`PnL neto contabilizado por día · ${data.currency} · ${data.timezone}`}
    >
      <div className="overflow-x-auto">
        <div className="min-w-[530px]">
          <div className="mb-2 grid grid-cols-7 gap-2">
            {["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].map((d) => (
              <div key={d} className="py-2 text-center text-xs text-slate-400">
                {d}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-2">
            {Array.from({ length: offset }, (_, i) => (
              <div key={`b${i}`} />
            ))}
            {days.map((d) => {
              const alpha = 0.14 + (Math.abs(d.pnl ?? 0) / max) * 0.32;
              const color =
                d.pnl > 0 ? "34,197,94" : d.pnl < 0 ? "239,68,68" : null;
              return (
                <div
                  key={d.date}
                  title={`${d.date}: ${signed(d.pnl)} ${data.currency}`}
                  className="flex min-h-[92px] flex-col rounded-xl border border-white/10 p-2"
                  style={{
                    background: color
                      ? `rgba(${color},${alpha})`
                      : d.pnl === null
                        ? "#101721"
                        : d.ledger_entries > 0
                          ? "#23334b"
                          : "#21262d",
                  }}
                >
                  <span className="text-xs text-slate-400">{d.day}</span>
                  <span
                    className={`my-auto text-center text-base font-bold tabular-nums ${d.pnl > 0 ? "text-green-400" : d.pnl < 0 ? "text-red-400" : "text-slate-500"}`}
                  >
                    {d.pnl === null
                      ? "—"
                      : d.pnl !== 0 || d.ledger_entries > 0
                        ? signed(d.pnl)
                        : ""}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <p className="mt-6 text-lg font-semibold">
        Resultado mensual:{" "}
        <span className={data.net_pnl >= 0 ? "text-green-400" : "text-red-400"}>
          {signed(data.net_pnl)} {data.currency}
        </span>
      </p>
      <dl className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-4">
        {info.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="mt-1 text-sm">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-5 text-xs text-slate-500">
        Verde: ganancia · Rojo: pérdida · Azul: resultado cero con movimientos ·
        Gris: sin movimientos · —: futuro/sin datos. Sin cierres no significa
        sin posiciones abiertas.
      </p>
    </Panel>
  );
}
