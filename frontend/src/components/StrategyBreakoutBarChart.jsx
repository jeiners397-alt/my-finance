import {
  BarChart,
  Bar,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { C, Panel, Empty, axis, tip, fmt, signed, number } from "./chartUtils";
export default function StrategyBreakoutBarChart({
  strategies = [],
  currency = "USDT",
  mode = "PAPER",
}) {
  const rows = strategies
    .map((r, i) => ({
      ...r,
      key: String(r.id ?? i),
      net_pnl: number(r.net_pnl),
    }))
    .filter((r) => r.net_pnl !== null);
  const extent =
    rows.reduce((max, r) => Math.max(max, Math.abs(r.net_pnl)), 1) * 1.15;
  const metrics = ({ x, y, payload }) => {
    const r = rows.find((r) => r.key === payload.value);
    return r ? (
      <g transform={`translate(${x + 10},${y})`}>
        <text fill="#e5e7eb" fontSize={12} y={-4}>
          {signed(r.net_pnl)} {currency} ({signed(r.pnl_pct)}%)
        </text>
        <text fill={C.muted} fontSize={11} y={15}>
          {fmt(r.trades, 0)} op · WR {fmt(r.win_rate, 0)}% · PF{" "}
          {fmt(r.profit_factor)}
        </text>
      </g>
    ) : null;
  };
  return (
    <Panel
      title={`Resultados por estrategia · ${mode}`}
      subtitle="Trades cerrados · PnL neto de costes · % sobre equidad inicial de la cuenta"
    >
      {!rows.length ? (
        <Empty />
      ) : (
        <div className="overflow-x-auto">
          <div
            style={{
              height: Math.max(260, rows.length * 78 + 55),
              minWidth: 800,
            }}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={rows}
                layout="vertical"
                barSize={36}
                margin={{ top: 8, right: 8, bottom: 25, left: 0 }}
                accessibilityLayer
              >
                <CartesianGrid stroke={C.grid} horizontal={false} />
                <XAxis
                  {...axis}
                  type="number"
                  domain={[-extent, extent]}
                  label={{
                    value: `PnL neto (${currency})`,
                    position: "bottom",
                    fill: C.muted,
                  }}
                />
                <YAxis
                  {...axis}
                  yAxisId="names"
                  dataKey="key"
                  type="category"
                  width={185}
                  interval={0}
                  tickFormatter={(v) => rows.find((r) => r.key === v)?.name}
                />
                <YAxis
                  yAxisId="metrics"
                  dataKey="key"
                  type="category"
                  orientation="right"
                  width={245}
                  interval={0}
                  axisLine={false}
                  tickLine={false}
                  tick={metrics}
                />
                <ReferenceLine yAxisId="names" x={0} stroke="#94a3b8" />
                <Tooltip
                  contentStyle={tip}
                  cursor={{ fill: "#ffffff05" }}
                  labelFormatter={(v) => rows.find((r) => r.key === v)?.name}
                  formatter={(v) => [`${signed(v)} ${currency}`, "PnL neto"]}
                />
                <Bar
                  yAxisId="names"
                  dataKey="net_pnl"
                  isAnimationActive={false}
                >
                  {rows.map((r) => (
                    <Cell key={r.key} fill={r.net_pnl >= 0 ? C.green : C.red} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </Panel>
  );
}
