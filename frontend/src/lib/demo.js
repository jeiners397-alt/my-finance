const names = [
  "Extreme Momentum",
  "Volatility Breakout",
  "Liquidity Sweep",
  "Exhaustion Reversal",
  "Micro Pullback",
];
export function demoData(month, timezone = "UTC", selectedId) {
  const [year, m] = month.split("-").map(Number),
    now = new Date();
  const todayKey = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
  const count = new Date(Date.UTC(year, m, 0)).getUTCDate();
  const days = [],
    trades = [],
    points = [];
  let balance = 100,
    peak = 100;
  const addPoint = (t) => {
    peak = Math.max(peak, balance);
    points.push({
      timestamp: new Date(t).toISOString(),
      equity: balance,
      peak_equity: peak,
      drawdown_pct: (balance / peak - 1) * 100,
    });
  };
  addPoint(Date.UTC(year, m - 1, 1));
  for (let d = 1; d <= count; d++) {
    const key = `${month}-${String(d).padStart(2, "0")}`,
      future = key > todayKey;
    const hasTrade = !future && d % 4 !== 0;
    const gross = hasTrade
      ? Number((Math.sin(d * 1.7) * 2.8 + 0.55).toFixed(4))
      : 0;
    const fee = hasTrade ? 0.04 : 0,
      net = Number((gross - fee).toFixed(4));
    days.push({
      date: key,
      net_pnl: future ? null : net,
      ledger_entries: future ? null : hasTrade ? 3 : 0,
      trades: future ? null : hasTrade ? 1 : 0,
      is_future: future,
    });
    if (!future) {
      for (let h = 0; h < 24; h += 2) {
        if (d === 1 && h === 0) continue;
        if (h === 12) balance = Number((balance + net).toFixed(4));
        addPoint(Date.UTC(year, m - 1, d, h));
      }
    }
    if (hasTrade)
      trades.push({
        id: d,
        symbol: d % 2 ? "BTCUSDT" : "ETHUSDT",
        side: d % 2 ? "LONG" : "SHORT",
        strategy_id: d % 5,
        strategy_name: names[d % 5],
        status: "CLOSED",
        net_pnl: net,
        gross,
      });
  }
  const strategies = names
    .map((name, id) => {
      const rows = trades.filter((t) => t.strategy_id === id),
        positive = rows.reduce((a, t) => a + Math.max(t.net_pnl, 0), 0),
        negative = rows.reduce((a, t) => a + Math.max(-t.net_pnl, 0), 0),
        wins = rows.filter((t) => t.net_pnl > 0).length;
      return {
        id,
        name,
        trades: rows.length,
        wins,
        losses: rows.filter((t) => t.net_pnl < 0).length,
        net_pnl: positive - negative,
        pnl_pct: positive - negative,
        win_rate: rows.length ? (wins / rows.length) * 100 : null,
        profit_factor: negative ? positive / negative : null,
      };
    })
    .filter((s) => s.trades);
  const selected =
    trades.find((t) => String(t.id) === String(selectedId)) ?? trades.at(-1);
  let trade = null;
  if (selected) {
    const entry = selected.symbol === "BTCUSDT" ? 68000 : 2600,
      sign = selected.side === "LONG" ? 1 : -1;
    const exit = entry + sign * selected.gross * 10,
      sl = entry - sign * 50,
      tp = entry + sign * 50;
    trade = {
      ...selected,
      entry_price: entry,
      initial_sl: sl,
      initial_tp: tp,
      exit_price: exit,
      exit_seconds: 240,
      exit_reason: "MANUAL",
      samples: Array.from({ length: 121 }, (_, i) => ({
        seconds_from_entry: i * 2,
        observed_price:
          entry +
          ((exit - entry) * i) / 120 +
          Math.sin(i * 0.28) * 7 * Math.sin((Math.PI * i) / 120),
        stop_loss: sl,
        take_profit: tp,
      })),
    };
  }
  return {
    demo: true,
    account: {
      id: 1,
      name: "A13 · Precision Scalper",
      currency: "USDT",
      mode: "DEMO",
      initial_capital: 100,
    },
    equity: { currency: "USDT", points },
    strategies: { strategies },
    calendar: {
      year,
      month: m,
      timezone,
      currency: "USDT",
      days,
      net_pnl: days.reduce((a, d) => a + (d.net_pnl ?? 0), 0),
      summary: { commissions: trades.length * 0.04, trades: trades.length },
    },
    trade,
    list: trades,
    telemetry: {
      stale: false,
      metric: {
        host_ref: "demo-vps",
        observed_at: now.toISOString(),
        cpu_pct: 11,
        ram_pct: 56,
        api_latency_ms: 84,
        db_status: "OK",
      },
    },
  };
}
