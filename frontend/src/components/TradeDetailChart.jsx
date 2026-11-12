import { Target, X } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
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
function Entry({ cx, cy }) {
  return (
    <path
      d={`M${cx - 7},${cy - 8} L${cx + 7},${cy - 8} L${cx},${cy + 5} Z`}
      fill="white"
    />
  );
}
function Exit({ cx, cy, target }) {
  const Icon = target ? Target : X;
  return (
    <g transform={`translate(${cx - 9},${cy - 9})`}>
      <Icon
        width={18}
        height={18}
        color={target ? C.green : C.red}
        strokeWidth={3}
      />
    </g>
  );
}
export default function TradeDetailChart({
  trade,
  samples = [],
  maxGapSeconds = 10,
}) {
  if (!trade)
    return (
      <Panel title="Detalle de operación">
        <Empty message="Selecciona una operación" />
      </Panel>
    );
  const entry = number(trade.entry_price),
    exit = number(trade.exit_price),
    seconds = number(trade.exit_seconds);
  const rows = samples
    .map((s) => ({
      t: number(s.seconds_from_entry),
      price: number(s.observed_price),
      sl: number(s.stop_loss === undefined ? trade.initial_sl : s.stop_loss),
      tp: number(
        s.take_profit === undefined ? trade.initial_tp : s.take_profit,
      ),
    }))
    .filter((s) => s.t !== null && s.t >= 0)
    .sort((a, b) => a.t - b.t);
  const plot = gaps(rows, "t", ["price", "sl", "tp"], maxGapSeconds);
  const yd = domain([
    entry,
    exit,
    trade.initial_sl,
    trade.initial_tp,
    ...rows.flatMap((s) => [s.price, s.sl, s.tp]),
  ]);
  const max = rows.reduce(
    (m, s) => Math.max(m, s.t),
    Math.max(1, seconds ?? 0),
  );
  return (
    <Panel
      title={`${trade.symbol} · ${trade.side} · ${trade.strategy_name}`}
      subtitle="Precios observados · SL/TP vigentes · Entrada y salida medias ponderadas por cantidad"
    >
      <div className="mb-4 flex flex-wrap gap-4 text-xs">
        <span className="text-blue-300">━ Precio</span>
        <span>━ Entrada {fmt(entry, 4)}</span>
        <span className="text-red-400">┄ Stop Loss</span>
        <span className="text-green-400">┄ Take Profit</span>
      </div>
      <div className="h-[380px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={plot}
            margin={{ top: 20, right: 25, bottom: 25, left: 0 }}
            accessibilityLayer
          >
            <CartesianGrid stroke={C.grid} />
            <XAxis
              {...axis}
              dataKey="t"
              type="number"
              domain={[0, max]}
              label={{
                value: "Segundos desde la entrada",
                position: "bottom",
                fill: C.muted,
              }}
            />
            <YAxis
              {...axis}
              width={85}
              domain={yd}
              tickFormatter={(v) => fmt(v, 4)}
            />
            <Tooltip
              contentStyle={tip}
              labelFormatter={(v) => `${fmt(v, 1)} segundos`}
              formatter={(v, n) => [fmt(v, 4), n]}
            />
            <Line
              name="Precio"
              dataKey="price"
              type="linear"
              stroke={C.blue}
              strokeWidth={2.3}
              dot={rows.length === 1}
              connectNulls={false}
              isAnimationActive={false}
            />
            {[
              ["sl", "Stop Loss", C.red],
              ["tp", "Take Profit", C.green],
            ].map(([key, name, color]) => (
              <Line
                key={key}
                dataKey={key}
                name={name}
                type="stepAfter"
                stroke={color}
                strokeDasharray="7 5"
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
            {entry !== null && (
              <>
                <ReferenceLine y={entry} stroke="#e2e8f0" />
                <ReferenceDot x={0} y={entry} shape={<Entry />} />
              </>
            )}
            {exit !== null && seconds !== null && (
              <ReferenceDot
                x={seconds}
                y={exit}
                shape={<Exit target={trade.exit_reason === "TARGET"} />}
                label={{
                  value: `Salida ${fmt(exit, 4)}`,
                  position: "insideTopRight",
                  fill: "#fff",
                  offset: 12,
                }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        No se interpolan intervalos sin muestras. Los marcadores no añaden
        precios observados.
      </p>
    </Panel>
  );
}
