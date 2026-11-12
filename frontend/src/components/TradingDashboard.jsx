import { Activity, Cpu, Database, Wallet } from "lucide-react";
import StrategyBreakoutBarChart from "./StrategyBreakoutBarChart";
import EquityDrawdownChart from "./EquityDrawdownChart";
import TradeDetailChart from "./TradeDetailChart";
import PnLCalendarGrid from "./PnLCalendarGrid";
import { Panel, fmt, signed } from "./chartUtils";
export default function TradingDashboard({ data, timezone, tradeSelector }) {
  const { account, equity, strategies, calendar, trade, telemetry } = data;
  const rows = strategies.strategies ?? [],
    count = rows.reduce((n, r) => n + r.trades, 0),
    wins = rows.reduce((n, r) => n + r.wins, 0),
    losses = rows.reduce((n, r) => n + r.losses, 0);
  const final = equity.points.at(-1),
    metric = telemetry.metric;
  const dd = equity.points.reduce(
    (m, p) => (p.drawdown_pct == null ? m : Math.min(m, p.drawdown_pct)),
    0,
  );
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  const daily = calendar.days.find((day) => day.date === today)?.net_pnl;
  const kpis = [
    [
      "Equidad al final del periodo",
      `${fmt(final?.equity)} ${account.currency}`,
    ],
    [
      "PnL mensual contabilizado",
      `${signed(calendar.net_pnl)} ${account.currency}`,
    ],
    [
      "Win Rate · trades cerrados",
      `${fmt(count ? (wins / count) * 100 : null, 1)}%`,
    ],
    [`PnL de hoy · ${timezone}`, `${signed(daily)} ${account.currency}`],
    ["Operaciones cerradas", String(count)],
    ["DD máximo del periodo", `${fmt(Math.abs(dd))}%`],
    ["Ganadoras / Perdedoras", `${wins} / ${losses}`],
    [
      "Comisiones del mes",
      `${fmt(calendar.summary?.commissions, 3)} ${account.currency}`,
    ],
  ];
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {kpis.map(([label, value], i) => (
          <div
            key={label}
            className="rounded-xl border border-slate-800 bg-slate-900/50 p-4"
          >
            <div className="flex items-center gap-2 text-xs text-slate-400">
              {i === 0 && <Wallet size={14} />}
              {label}
            </div>
            <div className="mt-3 text-xl font-semibold tabular-nums sm:text-2xl">
              {value}
            </div>
          </div>
        ))}
      </div>
      <EquityDrawdownChart
        data={equity}
        initialCapital={account.initial_capital}
        mode={account.mode}
        timezone={timezone}
        maxGapSeconds={data.demo ? 7200 : 120}
      />
      <StrategyBreakoutBarChart
        strategies={rows}
        currency={account.currency}
        mode={account.mode}
      />
      <Panel
        title="Explorar operaciones"
        subtitle="Incluye operaciones abiertas y cerradas"
      >
        {tradeSelector}
      </Panel>
      <TradeDetailChart trade={trade} samples={trade?.samples ?? []} />
      <PnLCalendarGrid data={calendar} />
      <Panel
        title="Telemetría del servidor"
        subtitle={
          metric
            ? `${metric.host_ref} · ${new Date(metric.observed_at).toLocaleString("es-PE", { timeZone: timezone })}`
            : "No se han recibido métricas"
        }
      >
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
          {[
            [Cpu, "CPU", `${fmt(metric?.cpu_pct, 1)}%`],
            [Activity, "RAM", `${fmt(metric?.ram_pct, 1)}%`],
            [Activity, "Latencia API", `${fmt(metric?.api_latency_ms, 0)} ms`],
            [Database, "Base de datos", metric?.db_status ?? "UNKNOWN"],
          ].map(([Icon, label, value]) => (
            <div key={label}>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <Icon size={14} />
                {label}
              </div>
              <div className="mt-2 font-semibold">{value}</div>
            </div>
          ))}
        </div>
        {telemetry.stale && (
          <p className="mt-4 text-xs text-amber-400">
            Telemetría ausente o antigua (más de 120 segundos).
          </p>
        )}
      </Panel>
    </div>
  );
}
