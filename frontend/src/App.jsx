import { useEffect, useState } from "react";
import { BarChart3, RefreshCw, Radio, FlaskConical } from "lucide-react";
import TradingDashboard from "./components/TradingDashboard";
import { loadDashboard } from "./lib/api";
import { demoData } from "./lib/demo";

const BASE = (
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");
export default function App() {
  const [demo, setDemo] = useState(true),
    [token, setToken] = useState(""),
    [accountId, setAccountId] = useState("1");
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7)),
    [timezone, setTimezone] = useState("UTC"),
    [tradeId, setTradeId] = useState("");
  const [connection, setConnection] = useState(null),
    [data, setData] = useState(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [reload, setReload] = useState(0);
  useEffect(() => {
    setData(null);
    setError("");
    if (demo) {
      setData(demoData(month, timezone, tradeId));
      setLoading(false);
      return;
    }
    if (!connection) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    let timer;
    async function refresh() {
      setLoading(true);
      try {
        const result = await loadDashboard({
          ...connection,
          month,
          timezone,
          tradeId,
          base: BASE,
          signal: controller.signal,
        });
        if (!controller.signal.aborted) {
          setData(result);
          setError("");
        }
      } catch (e) {
        if (!controller.signal.aborted) setError(e.message);
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
          timer = setTimeout(refresh, 15000);
        }
      }
    }
    refresh();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [demo, connection, month, timezone, tradeId, reload]);
  const select = (
    <select
      aria-label="Operación"
      value={data?.trade?.id ?? ""}
      onChange={(e) => setTradeId(e.target.value)}
      className="field w-full"
    >
      <option value="">Seleccionar operación</option>
      {data?.list.map((t) => (
        <option key={t.id} value={t.id}>
          #{t.id} · {t.symbol} · {t.side} · {t.strategy_name}
        </option>
      ))}
    </select>
  );
  return (
    <main className="min-h-screen bg-[#080d15] px-3 py-6 text-slate-100 sm:px-6">
      <div className="mx-auto max-w-7xl">
        <header className="mb-7 flex flex-wrap items-center justify-between gap-5">
          <div>
            <div className="flex items-center gap-3">
              <span className="rounded-xl bg-blue-500/10 p-2 text-blue-400">
                <BarChart3 />
              </span>
              <h1 className="text-2xl font-bold tracking-tight">
                My Finance
                <span className="ml-3 text-sm font-normal text-slate-500">
                  Trading Analytics
                </span>
              </h1>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Binance Futures / MT5 · Monitor de operaciones y rendimiento
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={demo}
            onClick={() => {
              setDemo(!demo);
              setTradeId("");
            }}
            className={`flex items-center gap-3 rounded-full border px-4 py-2 text-sm ${demo ? "border-amber-500/30 bg-amber-500/10 text-amber-300" : "border-blue-500/30 bg-blue-500/10 text-blue-300"}`}
          >
            {demo ? <FlaskConical size={16} /> : <Radio size={16} />}
            {demo ? "Modo Demo / Datos de prueba" : "Datos del backend"}
          </button>
        </header>
        {demo && (
          <div className="mb-5 rounded-xl border border-amber-700/30 bg-amber-500/5 px-4 py-3 text-xs text-amber-200">
            DEMOSTRACIÓN: datos sintéticos deterministas. No son resultados
            reales ni se conecta a un exchange.
          </div>
        )}
        <div className="mb-6 flex flex-wrap items-end gap-3">
          <label className="text-xs text-slate-400">
            Mes
            <input
              className="field mt-1 block"
              type="month"
              min="1970-01"
              max="9998-12"
              value={month}
              onChange={(e) => {
                if (e.target.value) setMonth(e.target.value);
              }}
            />
          </label>
          <label className="text-xs text-slate-400">
            Zona del calendario
            <select
              className="field mt-1 block"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            >
              <option>UTC</option>
              <option>America/Lima</option>
            </select>
          </label>
          <button
            className="field flex items-center gap-2"
            onClick={() => setReload((r) => r + 1)}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            Actualizar
          </button>
          <span className="pb-2 text-xs text-slate-500">
            Curva y estrategias: mes UTC · Backend: actualización cada 15 s
          </span>
        </div>
        {!demo && (
          <form
            className="mb-6 flex flex-wrap items-end gap-3 rounded-xl border border-slate-800 p-4"
            onSubmit={(e) => {
              e.preventDefault();
              setTradeId("");
              setConnection({ accountId: Number(accountId), token });
            }}
          >
            <label className="text-xs text-slate-400">
              Cuenta
              <input
                required
                type="number"
                min="1"
                className="field mt-1 block w-24"
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
              />
            </label>
            <label className="grow text-xs text-slate-400">
              Bearer Token del dashboard
              <input
                required
                type="password"
                minLength={32}
                autoComplete="off"
                className="field mt-1 block w-full"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Se conserva solo en memoria"
              />
            </label>
            <button className="field" type="submit">
              Conectar
            </button>
            <p className="w-full text-xs text-slate-500">
              No introduzcas claves de Binance/Exness. API: {BASE}
            </p>
          </form>
        )}
        {error && (
          <div
            role="alert"
            className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300"
          >
            {error}. Comprueba el backend, PostgreSQL y el token.{" "}
            {data ? "Se conservan los últimos datos recibidos." : ""}
          </div>
        )}
        {loading && !data && (
          <p role="status" className="py-20 text-center text-slate-400">
            Cargando datos…
          </p>
        )}
        {data ? (
          <TradingDashboard
            data={data}
            timezone={timezone}
            tradeSelector={select}
          />
        ) : (
          !loading && (
            <p className="py-20 text-center text-slate-500">
              Conecta tu cuenta o activa el modo demo.
            </p>
          )
        )}
        <footer className="py-8 text-center text-xs text-slate-600">
          My Finance · {demo ? "SIMULACIÓN" : "MONITORIZACIÓN"} · Sin ejecución
          de órdenes
        </footer>
      </div>
    </main>
  );
}
