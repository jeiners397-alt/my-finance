export async function getJSON(path, { base, token, signal }) {
  const response = await fetch(`${base}${path}`, {
    signal,
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : message;
    } catch {
      /* Non-JSON proxy response. */
    }
    throw new Error(message);
  }
  return response.json();
}

export async function paginate(path, field, options) {
  let result,
    cursor = null,
    previous = null,
    items = [];
  do {
    const separator = path.includes("?") ? "&" : "?";
    result = await getJSON(
      `${path}${cursor !== null ? `${separator}cursor=${encodeURIComponent(cursor)}` : ""}`,
      options,
    );
    items.push(...result[field]);
    previous = cursor;
    cursor = result.next_cursor;
    if (cursor !== null && cursor === previous)
      throw new Error("El servidor repitió el cursor de paginación");
  } while (cursor !== null && cursor !== undefined);
  return { ...result, [field]: items, next_cursor: null };
}

export async function loadDashboard({
  accountId,
  month,
  timezone,
  tradeId,
  ...options
}) {
  const [year, m] = month.split("-").map(Number);
  // Equity and strategy filters cover the selected UTC month. Calendar uses its explicit timezone.
  const start = new Date(Date.UTC(year, m - 1, 1)).toISOString();
  const end = new Date(Date.UTC(year, m, 1)).toISOString();
  const range = new URLSearchParams({ start, end }).toString();
  const [account, equity, strategies, calendar, telemetry, list] =
    await Promise.all([
      getJSON(`/accounts/${accountId}`, options),
      paginate(
        `/analytics/equity-curve/${accountId}?${range}`,
        "points",
        options,
      ),
      getJSON(`/analytics/strategies/${accountId}?${range}`, options),
      getJSON(
        `/analytics/calendar/${accountId}?${new URLSearchParams({ year, month: m, timezone })}`,
        options,
      ),
      getJSON("/telemetry/latest", options),
      paginate("/trades", "trades", options),
    ]);
  const selected = list.trades.some((t) => String(t.id) === String(tradeId))
    ? tradeId
    : list.trades.at(-1)?.id;
  const trade = selected
    ? await paginate(`/trades/${selected}`, "samples", options)
    : null;
  return {
    account,
    equity,
    strategies,
    calendar,
    telemetry,
    trade,
    list: list.trades,
    demo: false,
  };
}
