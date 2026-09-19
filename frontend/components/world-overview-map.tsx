"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import countries from "i18n-iso-countries";
import english from "i18n-iso-countries/langs/en.json";
import {
  ComposableMap,
  Geographies,
  Geography,
  Graticule,
  Sphere,
} from "react-simple-maps";
import worldGeography from "world-atlas/countries-110m.json";

import { fetchMetricMap, type MetricMapPoint } from "../lib/api";

countries.registerLocale(english);

const mapMetrics = [
  { key: "global_renewable_share_pct", label: "Renewable electricity share", domain: "energy", scale: "positive-pct" },
  { key: "global_clean_electricity_share_pct", label: "Clean electricity share", domain: "energy", scale: "positive-pct" },
  { key: "global_wind_solar_share_pct", label: "Wind and solar share", domain: "energy", scale: "positive-pct" },
  { key: "global_fossil_electricity_share_pct", label: "Fossil electricity share", domain: "energy", scale: "negative-pct" },
  { key: "freshwater_resources_per_capita_m3", label: "Renewable freshwater per person", domain: "freshwater", scale: "resources" },
  { key: "freshwater_withdrawals_pct_resources", label: "Withdrawals vs. internal resources", domain: "freshwater", scale: "pressure" },
  { key: "water_stress_pct", label: "Water stress", domain: "freshwater", scale: "pressure" },
  { key: "safe_drinking_water_access_pct", label: "Safely managed drinking-water access", domain: "freshwater", scale: "positive-pct" },
] as const;

type MapMetric = (typeof mapMetrics)[number];

function fillForValue(value: number | undefined, metric: MapMetric) {
  if (value === undefined) return "#273548";
  if (metric.scale === "negative-pct" || metric.scale === "pressure") {
    if (value < 25) return "#34d399";
    if (value < 50) return "#fbbf24";
    if (value < 75) return "#fb923c";
    return "#fb7185";
  }
  if (metric.scale === "resources") {
    if (value < 500) return "#fb7185";
    if (value < 1000) return "#fb923c";
    if (value < 1700) return "#fbbf24";
    if (value < 5000) return "#0891b2";
    return "#6ee7b7";
  }
  if (value < 10) return "#1e3a5f";
  if (value < 25) return "#0369a1";
  if (value < 50) return "#0891b2";
  if (value < 75) return "#10b981";
  return "#6ee7b7";
}

function alpha3FromNumeric(id: string | number) {
  return countries.numericToAlpha3(String(id).padStart(3, "0")) || undefined;
}

export function WorldOverviewMap() {
  const router = useRouter();
  const [metricKey, setMetricKey] = useState<string>(mapMetrics[0].key);
  const [points, setPoints] = useState<MetricMapPoint[]>([]);
  const [unit, setUnit] = useState("%");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [hoveredCode, setHoveredCode] = useState<string>();

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(undefined);
    fetchMetricMap(metricKey)
      .then((result) => {
        if (!active) return;
        setPoints(result.points);
        setUnit(result.unit);
      })
      .catch(() => active && setError("Country-level map data could not be loaded."))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [metricKey]);

  const byCode = useMemo(
    () => new Map(points.map((point) => [point.code, point])),
    [points],
  );
  const activeMetric = mapMetrics.find((metric) => metric.key === metricKey) ?? mapMetrics[0];
  const hovered = hoveredCode ? byCode.get(hoveredCode) : undefined;

  return (
    <section className="mt-8 overflow-hidden rounded-3xl border border-white/10 bg-slate-900/45 shadow-2xl shadow-black/10">
      <div className="flex flex-col gap-5 border-b border-white/10 px-7 py-7 sm:flex-row sm:items-end sm:justify-between sm:px-10">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-300">Geographic explorer</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">
            {activeMetric.domain === "freshwater" ? "Freshwater conditions by country" : "Electricity transition by country"}
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            Explore the latest available {activeMetric.domain === "freshwater" ? "World Bank water" : "Ember electricity"} observations. Gray means no matching observation—not a zero value.
          </p>
        </div>
        <label className="text-xs font-medium text-slate-300">
          Map metric
          <select
            value={metricKey}
            onChange={(event) => setMetricKey(event.target.value)}
            className="mt-2 block rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-sky-300/50"
          >
            {mapMetrics.map((metric) => (
              <option key={metric.key} value={metric.key}>{metric.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid lg:grid-cols-[1fr_240px]">
        <div className="relative bg-[radial-gradient(circle_at_center,rgba(14,165,233,0.10),transparent_55%)] px-3 py-4 sm:px-8">
          <ComposableMap
            projection="geoEqualEarth"
            projectionConfig={{ scale: 150 }}
            width={800}
            height={390}
            role="img"
            aria-label={`Country-level ${activeMetric.domain} metric map. Countries without observations are gray.`}
            className="relative mx-auto h-auto w-full max-w-5xl"
          >
            <Sphere id="earth-vitals-sphere" fill="#071426" stroke="#1e3a52" strokeWidth={0.8} />
            <Graticule fill="transparent" stroke="#1e3a52" strokeWidth={0.45} />
            <Geographies geography={worldGeography}>
              {({ geographies }) =>
                geographies.map((geography) => {
                  const code = alpha3FromNumeric(geography.id);
                  const point = code ? byCode.get(code) : undefined;
                  const fill = fillForValue(point?.value, activeMetric);
                  const label = point
                    ? `${point.name}: ${point.value.toFixed(1)} ${unit}`
                    : `${geography.properties.name}: no data`;
                  return (
                    <Geography
                      key={geography.rsmKey}
                      geography={geography}
                      fill={fill}
                      stroke="#071827"
                      strokeWidth={0.55}
                      tabIndex={0}
                      aria-label={label}
                      onMouseEnter={() => setHoveredCode(code)}
                      onMouseLeave={() => setHoveredCode(undefined)}
                      onFocus={() => setHoveredCode(code)}
                      onBlur={() => setHoveredCode(undefined)}
                      onClick={() => point && router.push(`/countries/${point.code}?domain=${activeMetric.domain}`)}
                      style={{
                        default: { outline: "none" },
                        hover: { fill: point ? "#f8fafc" : fill, outline: "none", cursor: point ? "pointer" : "default" },
                        pressed: { fill, outline: "none" },
                      }}
                    />
                  );
                })
              }
            </Geographies>
          </ComposableMap>
          {loading && <p className="absolute left-6 top-6 rounded-full bg-slate-950/80 px-3 py-1.5 text-xs text-slate-300">Loading country data…</p>}
          {error && <p role="alert" className="absolute left-6 top-6 rounded-xl bg-rose-950/90 px-3 py-2 text-xs text-rose-200">{error}</p>}
        </div>

        <aside className="border-t border-white/10 p-6 lg:border-l lg:border-t-0">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Country detail</p>
          {hovered ? (
            <div className="mt-5">
              <h3 className="text-lg font-semibold text-white">{hovered.name}</h3>
              <p className="mt-3 text-3xl font-semibold text-sky-200">{hovered.value.toFixed(1)} <span className="text-sm font-normal text-slate-400">{unit}</span></p>
              <p className="mt-2 text-xs text-slate-500">Latest: {hovered.timestamp}</p>
              <p className="mt-5 text-xs leading-5 text-slate-400">Click the country to open its complete electricity profile.</p>
            </div>
          ) : (
            <p className="mt-5 text-sm leading-6 text-slate-400">Hover or focus a country to inspect its latest value.</p>
          )}
          <div className="mt-8 space-y-2 text-xs text-slate-500">
            <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm bg-[#273548]" /> No observation</div>
            <div className={`h-2 rounded-full bg-gradient-to-r ${activeMetric.scale === "pressure" || activeMetric.scale === "negative-pct" ? "from-[#34d399] via-[#fbbf24] to-[#fb7185]" : "from-[#1e3a5f] via-[#0891b2] to-[#6ee7b7]"}`} />
            <div className="flex justify-between">
              <span>{activeMetric.scale === "resources" ? "Scarcer" : activeMetric.scale === "pressure" || activeMetric.scale === "negative-pct" ? "Lower pressure" : "Lower share"}</span>
              <span>{activeMetric.scale === "resources" ? "More abundant" : activeMetric.scale === "pressure" || activeMetric.scale === "negative-pct" ? "Higher pressure" : "Higher share"}</span>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
