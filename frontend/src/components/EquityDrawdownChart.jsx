import { useId } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  C,
  Panel,
  Empty,
  axis,
  tip,
  fmt,
  number,
  domain,
  gaps,
} from "./chartUtils";
export default function EquityDrawdownChart({
  data,
  initialCapital,
  mode = "PAPER",
  timezone = "UTC",
  maxGapSeconds = 120,
}) {
  const syncId = useId();
  const points = (data?.points ?? [])
    .map((p) => ({
      ...p,
      t: Date.parse(p.timestamp),
      equity: number(p.equity),
      drawdown_pct: number(p.drawdown_pct),
    }))
    .filter((p) => Number.isFinite(p.t))
    .sort((a, b) => a.t - b.t);
  const valid = points.filter((p) => p.equity !== null),
    last = valid.at(-1),
    capital = number(initialCapital),
    currency = data?.currency ?? "USDT";
  const plot = gaps(
    points,
    "t",
    ["equity", "drawdown_pct"],
    maxGapSeconds * 1000,
  );
  const dd = points.reduce(
    (m, p) => (p.drawdown_pct === null ? m : Math.min(m, p.drawdown_pct)),
    0,
  );
  const yd = domain([...valid.map((p) => p.equity), capital]);
  const xd = points.length
    ? [points[0].t, Math.max(points.at(-1).t, points[0].t + 1000)]
    : [0, 1];
  const df = new Intl.DateTimeFormat("es-PE", {
    timeZone: timezone,
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const xaxis = (
    <XAxis
      {...axis}
      dataKey="t"
      type="number"
      scale="time"
      domain={xd}
      tickFormatter={(v) => df.format(v)}
      minTickGap={65}
      height={38}
    />
  );
  const tooltip = (
    <Tooltip
      contentStyle={tip}
      labelFormatter={(v) => df.format(Number(v))}
      formatter={(v, n) => [`${fmt(v)} ${n === "DD" ? "%" : currency}`, n]}
    />
  );
  return (
    <Panel
      title={`Curva de equidad · ${mode}`}
      subtitle={`Equidad ${fmt(last?.equity)} ${currency} · DD máximo del periodo ${fmt(Math.abs(dd))}% · ${timezone}`}
    >
      {!last ? (
        <Empty />
      ) : (
        <>
          <div className="mb-3 flex flex-wrap gap-5 text-xs text-slate-400">
            <span className="text-blue-300">━ Equidad</span>
            <span>
              ┄ Capital inicial {fmt(capital)} {currency}
            </span>
          </div>
          <div className="h-[330px] sm:h-[380px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={plot}
                syncId={syncId}
                syncMethod="value"
                margin={{ top: 22, right: 25, left: 0, bottom: 0 }}
                accessibilityLayer
              >
                <CartesianGrid stroke={C.grid} />
                {xaxis}
                <YAxis
                  {...axis}
                  width={72}
                  domain={yd}
                  tickFormatter={(v) => fmt(v)}
                />
                {tooltip}
                <Area
                  dataKey="equity"
                  type="linear"
                  baseValue={yd[0]}
                  fill={C.blue}
                  fillOpacity={0.09}
                  stroke="none"
                  tooltipType="none"
                  connectNulls={false}
                  isAnimationActive={false}
                />
                <Line
                  name="Equidad"
                  dataKey="equity"
                  type="linear"
                  stroke={C.blue}
                  strokeWidth={2.4}
                  dot={valid.length < 50 ? { r: 2 } : false}
                  connectNulls={false}
                  isAnimationActive={false}
                />
                {capital !== null && (
                  <ReferenceLine
                    y={capital}
                    stroke="#a1a1aa"
                    strokeDasharray="6 5"
                  />
                )}
                <ReferenceDot
                  x={last.t}
                  y={last.equity}
                  r={5}
                  fill={C.blue}
                  stroke="#0d1117"
                  label={{
                    value: `${fmt(last.equity)} ${currency}`,
                    position: "insideTopRight",
                    offset: 12,
                    fill: "#fff",
                    fontWeight: 700,
                  }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="h-[155px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={plot}
                syncId={syncId}
                syncMethod="value"
                margin={{ top: 12, right: 25, left: 0, bottom: 0 }}
                accessibilityLayer
              >
                <CartesianGrid stroke={C.grid} />
                {xaxis}
                <YAxis
                  {...axis}
                  width={72}
                  domain={[Math.min(-1, dd * 1.1), 0]}
                  tickFormatter={(v) => `${fmt(v, 1)}%`}
                />
                {tooltip}
                <Area
                  name="DD"
                  dataKey="drawdown_pct"
                  type="linear"
                  baseValue={0}
                  stroke={C.red}
                  fill={C.red}
                  fillOpacity={0.35}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Drawdown sobre equidad sin ajustar depósitos/retiros. Los huecos
            indican falta de muestras.
          </p>
        </>
      )}
    </Panel>
  );
}
