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
  type Domain,
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

type CountryDomain = Extract<Domain, "energy" | "freshwater">;

const domainAppearance = {
  energy: {
    label: "Electricity",
    eyebrow: "text-amber-300",
    border: "border-amber-400/30",
    wash: "from-amber-400/10",
    badge: "bg-amber-400/10 text-amber-200 ring-amber-400/25",
    line: "#fbbf24",
  },
  freshwater: {
    label: "Freshwater",
    eyebrow: "text-cyan-300",
    border: "border-cyan-400/30",
    wash: "from-cyan-400/10",
    badge: "bg-cyan-400/10 text-cyan-200 ring-cyan-400/25",
    line: "#22d3ee",
  },
} as const;

export function CountryDashboard({ code, initialDomain = "energy" }: { code: string; initialDomain?: CountryDomain }) {
  const [country, setCountry] = useState<Geography>();
  const [allMetrics, setAllMetrics] = useState<DomainMetric[]>([]);
  const [selectedDomain, setSelectedDomain] = useState<CountryDomain>(initialDomain);
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
        setAllMetrics(metricResult);
      })
      .catch(() => active && setError("This country profile could not be loaded."))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [code]);

  const metrics = allMetrics.filter((metric) => metric.domain === selectedDomain);
  const appearance = domainAppearance[selectedDomain];

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
      <div className={`mt-6 rounded-3xl border ${appearance.border} bg-gradient-to-br ${appearance.wash} via-slate-950 to-slate-950 px-7 py-10 sm:px-10`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${appearance.eyebrow}`}>Country environmental profile / {country.code}</p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight text-white sm:text-5xl">{country.name}</h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-slate-400">
          Country-level electricity and freshwater observations, with historical series and source context for every available indicator.
        </p>
      </div>

      <div className="mt-8 flex gap-2" aria-label="Country data domain">
        {(["energy", "freshwater"] as CountryDomain[]).map((domain) => (
          <button
            key={domain}
            type="button"
            aria-pressed={selectedDomain === domain}
            onClick={() => {
              setSelectedDomain(domain);
              setExpandedKey(undefined);
            }}
            className={`rounded-full px-4 py-2 text-sm ring-1 ring-inset transition ${selectedDomain === domain ? domainAppearance[domain].badge : "bg-slate-900 text-slate-400 ring-white/10 hover:text-white"}`}
          >
            {domainAppearance[domain].label}
          </button>
        ))}
      </div>

      <div className="mb-6 mt-12 flex items-end justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Country observations</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">{appearance.label} vital signs</h2>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs ring-1 ring-inset ${appearance.badge}`}>{metrics.length} metrics</span>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {metrics.map((metric) => {
          const expanded = expandedKey === metric.key;
          const chartData = (histories[metric.key] ?? []).map((point) => ({
            year: Number(point.timestamp.slice(0, 4)),
            value: point.value,
          }));
          return (
            <article key={metric.key} className={`overflow-hidden rounded-2xl border bg-slate-900/60 ${expanded ? appearance.border : "border-white/10"}`}>
              <button type="button" onClick={() => void toggleMetric(metric)} aria-expanded={expanded} className="w-full p-6 text-left">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${appearance.eyebrow}`}>{metric.cadence}</p>
                    <h3 className="mt-3 text-base font-medium text-slate-200">{metric.display_name.replace(/^Global /, "")}</h3>
                  </div>
                  <span className={`grid h-8 w-8 place-items-center rounded-full transition ${appearance.badge} ${expanded ? "rotate-45" : ""}`}>+</span>
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
                          <Line type="monotone" dataKey="value" stroke={appearance.line} strokeWidth={3} dot={{ r: 3, fill: appearance.line, strokeWidth: 0 }} />
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
      {metrics.length === 0 && (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-8 text-slate-400">No {selectedDomain} observations are available for this country.</div>
      )}
    </main>
  );
}
