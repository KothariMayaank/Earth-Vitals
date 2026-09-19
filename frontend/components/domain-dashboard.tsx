"use client";

import { useEffect, useMemo, useState } from "react";
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
  type Domain,
  type DomainMetric,
  type HistoryPoint,
  type MetricProjection,
  createMetricProjection,
  fetchDomainSummary,
  fetchMetricHistory,
} from "../lib/api";

const domainStyles = {
  energy: {
    label: "Energy",
    description: "Tracking how the world generates electricity and moves toward cleaner power.",
    color: "#fbbf24",
    eyebrow: "text-amber-300",
    wash: "from-amber-400/15",
    border: "border-amber-400/25",
    badge: "bg-amber-400/10 text-amber-200 ring-amber-400/25",
  },
  minerals: {
    label: "Minerals",
    description: "Monitoring the finite reserves behind infrastructure, industry, and electrification.",
    color: "#d6d3d1",
    eyebrow: "text-stone-300",
    wash: "from-stone-300/15",
    border: "border-stone-300/25",
    badge: "bg-stone-300/10 text-stone-200 ring-stone-300/25",
  },
  emissions: {
    label: "Emissions",
    description: "Reading the atmosphere through globally aggregated air-quality measurements.",
    color: "#38bdf8",
    eyebrow: "text-sky-300",
    wash: "from-sky-400/15",
    border: "border-sky-400/25",
    badge: "bg-sky-400/10 text-sky-200 ring-sky-400/25",
  },
  freshwater: {
    label: "Freshwater",
    description: "Tracking renewable water availability, withdrawal pressure, and access to safe drinking water.",
    color: "#22d3ee",
    eyebrow: "text-cyan-300",
    wash: "from-cyan-400/15",
    border: "border-cyan-400/25",
    badge: "bg-cyan-400/10 text-cyan-200 ring-cyan-400/25",
  },
} as const;

const numberFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

function formatDate(date: string) {
  return new Intl.DateTimeFormat("en-US", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00Z`));
}

function LoadingCards() {
  return (
    <div className="grid gap-5 md:grid-cols-2" aria-label="Loading metrics" aria-busy="true">
      {[0, 1].map((item) => (
        <div key={item} className="animate-pulse rounded-2xl border border-white/10 bg-slate-900/50 p-6">
          <div className="h-3 w-24 rounded bg-slate-700" />
          <div className="mt-8 h-8 w-44 rounded bg-slate-700" />
          <div className="mt-5 h-3 w-32 rounded bg-slate-800" />
        </div>
      ))}
    </div>
  );
}

type ChartPanelProps = {
  metric: DomainMetric;
  points?: HistoryPoint[];
  loading: boolean;
  error?: string;
  color: string;
};

const finiteResourceMetrics = new Set([
  "global_oil_reserves_billion_barrels",
  "global_lithium_reserves_tonnes",
  "global_copper_reserves_tonnes",
  "global_cobalt_reserves_tonnes",
  "global_nickel_reserves_tonnes",
]);

const projectableMetrics = new Set([
  ...Array.from(finiteResourceMetrics),
  "global_renewable_share_pct",
  "global_electricity_generation_twh",
  "global_clean_electricity_share_pct",
  "global_fossil_electricity_share_pct",
  "global_wind_solar_share_pct",
  "reporting_station_pm25_mean_ug_m3",
  "global_atmospheric_co2_ppm",
  "global_atmospheric_co2_growth_ppm_per_year",
]);

function metricCategory(metric: DomainMetric) {
  if (metric.domain === "energy") {
    return metric.key.includes("share") ? "Electricity mix" : "Generation";
  }
  if (metric.domain === "minerals") {
    if (metric.key.includes("reserve_life")) return "Supply outlook";
    if (metric.key.includes("production")) return "Production";
    return "Reserves";
  }
  if (metric.domain === "freshwater") {
    if (metric.key.includes("access")) return "Water access";
    if (metric.key.includes("stress") || metric.key.includes("pct_resources")) return "Water pressure";
    return "Water availability";
  }
  return metric.key.includes("atmospheric_co2") ? "Climate gases" : "Air quality";
}

function ChartPanel({ metric, points, loading, error, color }: ChartPanelProps) {
  const finiteResource = finiteResourceMetrics.has(metric.key);
  const projectable = projectableMetrics.has(metric.key);
  const baselineYear = Number(metric.timestamp.slice(0, 4));
  const [rate, setRate] = useState(0);
  const [targetYear, setTargetYear] = useState(Math.max(2050, baselineYear + 25));
  const [projection, setProjection] = useState<MetricProjection>();
  const [projectionLoading, setProjectionLoading] = useState(false);
  const [projectionError, setProjectionError] = useState<string>();

  useEffect(() => {
    if (!projectable || loading || error || !points?.length) return;
    const timeout = window.setTimeout(async () => {
      setProjectionLoading(true);
      setProjectionError(undefined);
      try {
        const result = await createMetricProjection(
          metric.key,
          rate,
          finiteResource ? undefined : targetYear,
        );
        setProjection(result);
      } catch {
        setProjectionError("This scenario could not be computed. Check the API and try again.");
      } finally {
        setProjectionLoading(false);
      }
    }, 500);
    return () => window.clearTimeout(timeout);
  }, [error, finiteResource, loading, metric.key, points, projectable, rate, targetYear]);

  if (loading) {
    return <div className="grid h-72 place-items-center text-sm text-slate-400">Loading historical data…</div>;
  }
  if (error) {
    return <div className="grid h-72 place-items-center px-6 text-center text-sm text-rose-300">{error}</div>;
  }
  if (!points?.length) {
    return <div className="grid h-72 place-items-center text-sm text-slate-400">No history is available yet.</div>;
  }

  const chartYears = new Map<number, { year: number; observed?: number; projected?: number }>();
  for (const point of points) {
    const year = Number(point.timestamp.slice(0, 4));
    chartYears.set(year, { ...chartYears.get(year), year, observed: point.value });
  }
  for (const point of projection?.series ?? []) {
    chartYears.set(point.year, {
      ...chartYears.get(point.year),
      year: point.year,
      projected: point.value,
    });
  }
  const chartData = Array.from(chartYears.values()).sort((a, b) => a.year - b.year);

  return (
    <div className="w-full pt-6">
      <div className="h-72" aria-label={`${metric.display_name} observed and projected chart`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="4 4" vertical={false} />
            <XAxis
              dataKey="year"
              stroke="#64748b"
              tick={{ fill: "#94a3b8", fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              width={66}
              tickFormatter={(value: number) => numberFormatter.format(value)}
              stroke="#64748b"
              tick={{ fill: "#94a3b8", fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              formatter={(value: number, name: string) => [
                `${numberFormatter.format(value)} ${metric.unit}`,
                name === "projected" ? "Projected" : "Observed",
              ]}
              labelFormatter={(label: number) => `Year ${label}`}
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: "12px" }}
              labelStyle={{ color: "#cbd5e1" }}
            />
            <Line
              type="monotone"
              dataKey="observed"
              stroke={color}
              strokeWidth={3}
              dot={{ r: 3, fill: color, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: color, stroke: "#020617", strokeWidth: 2 }}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="projected"
              stroke={color}
              strokeWidth={2}
              strokeDasharray="7 6"
              dot={false}
              activeDot={{ r: 4, fill: color }}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mx-2 mt-5 rounded-xl border border-white/10 bg-slate-950/40 p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">About this metric</p>
        <p className="mt-2 text-sm leading-6 text-slate-300">
          {metric.description ?? "No additional methodology description is available."}
        </p>
        <a
          href={metric.source_url}
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-flex text-xs font-medium text-sky-300 hover:text-sky-200"
        >
          Source: {metric.source_name} ↗
        </a>
      </div>

      {projectable ? (
      <section className="mx-2 mt-5 rounded-xl border border-white/10 bg-slate-950/55 p-5" aria-label={`Project ${metric.display_name} forward`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Scenario explorer</p>
            <h4 className="mt-1 font-medium text-white">Project forward</h4>
          </div>
          <span className="text-xs text-slate-500" aria-live="polite">
            {projectionLoading ? "Computing…" : projection ? "Scenario saved" : "Waiting"}
          </span>
        </div>

        <div className="mt-5 grid gap-5 sm:grid-cols-[1fr_auto]">
          <div>
            <div className="mb-2 flex justify-between gap-3 text-xs">
              <label htmlFor={`${metric.key}-rate`} className="text-slate-300">
                Annual change in {finiteResource ? "extraction" : "value"}
              </label>
              <span className="tabular-nums text-white">{rate > 0 ? "+" : ""}{rate.toFixed(1)}%</span>
            </div>
            <input
              id={`${metric.key}-rate`}
              type="range"
              min="-10"
              max="10"
              step="0.5"
              value={rate}
              onChange={(event) => setRate(Number(event.target.value))}
              className="h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-700"
              style={{ accentColor: color }}
            />
          </div>
          {!finiteResource && (
            <div>
              <label htmlFor={`${metric.key}-year`} className="mb-2 block text-xs text-slate-300">Target year</label>
              <input
                id={`${metric.key}-year`}
                type="number"
                min={baselineYear + 1}
                max={baselineYear + 200}
                value={targetYear}
                onChange={(event) => setTargetYear(Number(event.target.value))}
                className="w-28 rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-white/30"
              />
            </div>
          )}
        </div>

        {projectionError && <p role="alert" className="mt-5 text-sm text-rose-300">{projectionError}</p>}
        {projection && !projectionError && (
          <div className="mt-5 border-t border-white/10 pt-5">
            <p className="text-sm font-medium leading-6 text-slate-200">{projection.result_summary}</p>
            <p className="mt-3 text-xs leading-5 text-slate-500">
              <span className="font-semibold uppercase tracking-wide text-slate-400">Methodology:</span>{" "}
              {projection.methodology_note}
            </p>
          </div>
        )}
      </section>
      ) : (
        <p className="mx-2 mt-4 text-xs leading-5 text-slate-500">
          This metric is shown as observational context and is not assigned a projection model.
        </p>
      )}
    </div>
  );
}

export function DomainDashboard({ domain }: { domain: Domain }) {
  const style = domainStyles[domain];
  const [metrics, setMetrics] = useState<DomainMetric[]>([]);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState<string>();
  const [expandedKey, setExpandedKey] = useState<string>();
  const [histories, setHistories] = useState<Record<string, HistoryPoint[]>>({});
  const [historyLoading, setHistoryLoading] = useState<string>();
  const [historyErrors, setHistoryErrors] = useState<Record<string, string>>({});
  const [selectedCategory, setSelectedCategory] = useState("All");

  useEffect(() => {
    let active = true;
    setSummaryLoading(true);
    setSummaryError(undefined);
    setSelectedCategory("All");
    fetchDomainSummary(domain)
      .then((data) => active && setMetrics(data))
      .catch(() => active && setSummaryError("We couldn't reach the Earth Vitals API. Make sure FastAPI is running on port 8000, then refresh this page."))
      .finally(() => active && setSummaryLoading(false));
    return () => {
      active = false;
    };
  }, [domain]);

  const categories = useMemo(
    () => ["All", ...Array.from(new Set(metrics.map(metricCategory)))],
    [metrics],
  );
  const visibleMetrics = selectedCategory === "All"
    ? metrics
    : metrics.filter((metric) => metricCategory(metric) === selectedCategory);

  async function toggleMetric(metric: DomainMetric) {
    if (expandedKey === metric.key) {
      setExpandedKey(undefined);
      return;
    }
    setExpandedKey(metric.key);
    if (histories[metric.key]) return;

    setHistoryLoading(metric.key);
    setHistoryErrors((current) => ({ ...current, [metric.key]: "" }));
    try {
      const points = await fetchMetricHistory(metric.key);
      setHistories((current) => ({ ...current, [metric.key]: points }));
    } catch {
      setHistoryErrors((current) => ({ ...current, [metric.key]: "Historical data could not be loaded. Please try again." }));
    } finally {
      setHistoryLoading(undefined);
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-14 lg:px-8 lg:py-20">
      <div className={`relative overflow-hidden rounded-3xl border ${style.border} bg-gradient-to-br ${style.wash} via-slate-950 to-slate-950 px-7 py-10 sm:px-10`}>
        <div className="absolute -right-16 -top-24 h-64 w-64 rounded-full border border-white/5" />
        <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${style.eyebrow}`}>Earth system / {style.label}</p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight text-white sm:text-5xl">{style.label} vital signs</h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-slate-400">{style.description}</p>
      </div>

      <div className="mb-6 mt-12 flex items-end justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Latest observations</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">Current readings</h2>
        </div>
        {!summaryLoading && !summaryError && (
          <span className={`rounded-full px-3 py-1 text-xs ring-1 ring-inset ${style.badge}`}>{metrics.length} metrics</span>
        )}
      </div>

      {summaryLoading && <LoadingCards />}
      {summaryError && (
        <div role="alert" className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.06] px-6 py-8 text-rose-200">
          <h2 className="font-semibold">Data temporarily unavailable</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-rose-200/70">{summaryError}</p>
        </div>
      )}
      {!summaryLoading && !summaryError && metrics.length === 0 && (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-8 text-slate-400">No metrics have been ingested for this domain yet.</div>
      )}

      {!summaryLoading && !summaryError && metrics.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2" aria-label="Metric categories">
          {categories.map((category) => (
            <button
              key={category}
              type="button"
              onClick={() => setSelectedCategory(category)}
              className={`rounded-full px-4 py-2 text-xs font-medium ring-1 ring-inset transition ${
                selectedCategory === category
                  ? style.badge
                  : "bg-slate-900/60 text-slate-400 ring-white/10 hover:text-white"
              }`}
            >
              {category}
            </button>
          ))}
        </div>
      )}

      <div className="grid gap-5 md:grid-cols-2">
        {visibleMetrics.map((metric) => {
          const expanded = expandedKey === metric.key;
          return (
            <article
              key={metric.key}
              className={`overflow-hidden rounded-2xl border bg-slate-900/60 shadow-xl shadow-black/10 transition ${expanded ? style.border : "border-white/10 hover:border-white/20"}`}
            >
              <button
                type="button"
                className="w-full p-6 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-white"
                onClick={() => void toggleMetric(metric)}
                aria-expanded={expanded}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${style.eyebrow}`}>
                      {metricCategory(metric)} · {metric.cadence}
                    </p>
                    <h3 className="mt-3 text-base font-medium text-slate-200">{metric.display_name}</h3>
                  </div>
                  <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ring-1 ring-inset transition ${style.badge} ${expanded ? "rotate-45" : ""}`}>+</span>
                </div>
                <p className="mt-7 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                  {numberFormatter.format(metric.value)} <span className="text-base font-normal text-slate-400">{metric.unit}</span>
                </p>
                <p className="mt-4 text-xs text-slate-500">Updated {formatDate(metric.timestamp)}</p>
              </button>

              {expanded && (
                <div className="border-t border-white/10 px-3 pb-4 sm:px-5">
                  <ChartPanel
                    metric={metric}
                    points={histories[metric.key]}
                    loading={historyLoading === metric.key}
                    error={historyErrors[metric.key]}
                    color={style.color}
                  />
                </div>
              )}
            </article>
          );
        })}
      </div>
    </main>
  );
}
