"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  fetchCountry,
  fetchCountryMetricHistory,
  fetchCountrySummary,
  type DomainMetric,
  type Geography,
  type HistoryPoint,
} from "../lib/api";


const numberFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

export function CountryDashboard({ code }: { code: string }) {
  const [country, setCountry] = useState<Geography>();
  const [metrics, setMetrics] = useState<DomainMetric[]>([]);
  const [expandedKey, setExpandedKey] = useState<string>();
  const [histories, setHistories] = useState<Record<string, HistoryPoint[]>>({});
  const [loadingKey, setLoadingKey] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([fetchCountry(code), fetchCountrySummary(code)])
      .then(([countryResult, metricResult]) => {
        if (!active) return;
        setCountry(countryResult);
        setMetrics(metricResult.filter((metric) => metric.domain === "energy"));
      })
      .catch(() => active && setError("This country profile could not be loaded."))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [code]);

  async function toggleMetric(metric: DomainMetric) {
    if (expandedKey === metric.key) {
      setExpandedKey(undefined);
      return;
    }
    setExpandedKey(metric.key);
    if (histories[metric.key]) return;
    setLoadingKey(metric.key);
    try {
      const points = await fetchCountryMetricHistory(code, metric.key);
      setHistories((current) => ({ ...current, [metric.key]: points }));
    } finally {
      setLoadingKey(undefined);
    }
  }

  if (loading) {
    return <main className="mx-auto max-w-7xl px-6 py-20 text-slate-400">Loading country profile…</main>;
  }
  if (error || !country) {
    return <main className="mx-auto max-w-7xl px-6 py-20 text-rose-300">{error}</main>;
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-14 lg:px-8 lg:py-20">
      <Link href="/" className="text-sm text-sky-300 hover:text-sky-200">← Back to world map</Link>
      <div className="mt-6 rounded-3xl border border-amber-400/25 bg-gradient-to-br from-amber-400/10 via-slate-950 to-slate-950 px-7 py-10 sm:px-10">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-amber-300">Country electricity profile / {country.code}</p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight text-white sm:text-5xl">{country.name}</h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-slate-400">
          Latest electricity mix and generation observations from Ember, with historical series for every available indicator.
        </p>
      </div>

      <div className="mb-6 mt-12 flex items-end justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Country observations</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">Electricity vital signs</h2>
        </div>
        <span className="rounded-full bg-amber-400/10 px-3 py-1 text-xs text-amber-200 ring-1 ring-inset ring-amber-400/25">{metrics.length} metrics</span>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {metrics.map((metric) => {
          const expanded = expandedKey === metric.key;
          const chartData = (histories[metric.key] ?? []).map((point) => ({
            year: Number(point.timestamp.slice(0, 4)),
            value: point.value,
          }));
          return (
            <article key={metric.key} className={`overflow-hidden rounded-2xl border bg-slate-900/60 ${expanded ? "border-amber-400/30" : "border-white/10"}`}>
              <button type="button" onClick={() => void toggleMetric(metric)} aria-expanded={expanded} className="w-full p-6 text-left">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-300">{metric.cadence}</p>
                    <h3 className="mt-3 text-base font-medium text-slate-200">{metric.display_name.replace(/^Global /, "")}</h3>
                  </div>
                  <span className={`grid h-8 w-8 place-items-center rounded-full bg-amber-400/10 text-amber-200 transition ${expanded ? "rotate-45" : ""}`}>+</span>
                </div>
                <p className="mt-7 text-3xl font-semibold text-white">{numberFormatter.format(metric.value)} <span className="text-base font-normal text-slate-400">{metric.unit}</span></p>
                <p className="mt-4 text-xs text-slate-500">Updated {formatDate(metric.timestamp)}</p>
              </button>

              {expanded && (
                <div className="border-t border-white/10 px-5 py-6">
                  {loadingKey === metric.key ? (
                    <div className="grid h-64 place-items-center text-sm text-slate-400">Loading history…</div>
                  ) : (
                    <div className="h-64" aria-label={`${country.name} ${metric.display_name} history`}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
                          <CartesianGrid stroke="#1e293b" strokeDasharray="4 4" vertical={false} />
                          <XAxis dataKey="year" tick={{ fill: "#94a3b8", fontSize: 12 }} tickLine={false} axisLine={false} />
                          <YAxis width={66} tickFormatter={(value: number) => numberFormatter.format(value)} tick={{ fill: "#94a3b8", fontSize: 12 }} tickLine={false} axisLine={false} />
                          <Tooltip formatter={(value: number) => [`${numberFormatter.format(value)} ${metric.unit}`, "Observed"]} labelFormatter={(year: number) => `Year ${year}`} contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: "12px" }} />
                          <Line type="monotone" dataKey="value" stroke="#fbbf24" strokeWidth={3} dot={{ r: 3, fill: "#fbbf24", strokeWidth: 0 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                  <p className="mt-4 text-sm leading-6 text-slate-300">{metric.description}</p>
                  <a href={metric.source_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex text-xs font-medium text-sky-300 hover:text-sky-200">Source: {metric.source_name} ↗</a>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </main>
  );
}
