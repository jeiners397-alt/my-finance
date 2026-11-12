import test from "node:test";
import assert from "node:assert/strict";
import { number, domain, gaps, monthDays } from "./data.js";
import { demoData } from "./demo.js";
import { paginate } from "./api.js";
test("missing values never become zero prices", () => {
  assert.equal(number(null), null);
  assert.equal(number(""), null);
  assert.equal(number("1.25"), 1.25);
  assert.deepEqual(domain([]), [0, 1]);
});
test("missing telemetry splits lines", () => {
  const r = gaps(
    [
      { t: 0, p: 2 },
      { t: 20, p: 3 },
    ],
    "t",
    ["p"],
    10,
  );
  assert.equal(r[1].p, null);
  assert.equal(r[1].t, 10);
});
test("leap month and missing days", () => {
  const d = monthDays({ year: 2024, month: 2, days: [] });
  assert.equal(d.length, 29);
  assert.equal(d[28].date, "2024-02-29");
  assert.equal(d[0].pnl, null);
});
test("demo equity, calendar and strategy net results reconcile", () => {
  const d = demoData("2026-01");
  const total = d.strategies.strategies.reduce((a, s) => a + s.net_pnl, 0);
  assert.ok(Math.abs(total - d.calendar.net_pnl) < 1e-8);
  assert.ok(Math.abs(d.equity.points.at(-1).equity - 100 - total) < 1e-8);
  assert.equal(d.calendar.summary.trades, d.list.length);
});
test("pagination collects all pages and sends bearer token", async () => {
  const old = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async (url, init) => {
    assert.equal(init.headers.Authorization, "Bearer fake");
    calls++;
    return {
      ok: true,
      json: async () => ({
        points: [calls],
        next_cursor: calls === 1 ? "next" : null,
      }),
    };
  };
  try {
    const r = await paginate("/curve", "points", {
      base: "http://test",
      token: "fake",
    });
    assert.deepEqual(r.points, [1, 2]);
  } finally {
    globalThis.fetch = old;
  }
});
