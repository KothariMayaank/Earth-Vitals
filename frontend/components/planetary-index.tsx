"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  type IndexDomain,
  type IndexValues,
  type PlanetaryIndex,
  fetchPlanetaryIndex,
  updateIndexWeights,
} from "../lib/api";

const domains: IndexDomain[] = ["energy", "minerals", "emissions", "freshwater"];
const domainMeta = {
  energy: { label: "Energy", color: "#fbbf24", text: "text-amber-300" },
  minerals: { label: "Minerals", color: "#d6d3d1", text: "text-stone-300" },
  emissions: { label: "Emissions", color: "#38bdf8", text: "text-sky-300" },
  freshwater: { label: "Freshwater", color: "#22d3ee", text: "text-cyan-300" },
};

function rebalanceWeights(current: IndexValues, changed: IndexDomain, nextValue: number): IndexValues {
  const clamped = Math.max(0, Math.min(1, nextValue));
  const otherDomains = domains.filter((domain) => domain !== changed);
  const available = 1 - clamped;
  const currentOtherTotal = otherDomains.reduce((sum, domain) => sum + current[domain], 0);
  const next = { ...current, [changed]: clamped };

  for (const domain of otherDomains) {
    next[domain] = currentOtherTotal > 0
      ? available * (current[domain] / currentOtherTotal)
      : available / otherDomains.length;
  }
  return next;
}

function scoreColor(score: number) {
  if (score >= 70) return "#34d399";
  if (score >= 40) return "#fbbf24";
  return "#fb7185";
}

export function PlanetaryHealthIndex() {
  const [index, setIndex] = useState<PlanetaryIndex>();
  const [weights, setWeights] = useState<IndexValues>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const hasUserChange = useRef(false);

  useEffect(() => {
    let active = true;
    fetchPlanetaryIndex()
      .then((result) => {
        if (!active) return;
        setIndex(result);
        setWeights(result.weights);
      })
      .catch(() => active && setError("The index could not be loaded. Make sure the FastAPI server and index weights are available."))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!weights || !hasUserChange.current) return;
    const timeout = window.setTimeout(async () => {
      setSaving(true);
      setError(undefined);
      try {
        const result = await updateIndexWeights(weights);
        setIndex(result);
        setWeights(result.weights);
        hasUserChange.current = false;
      } catch {
        setError("The new weights could not be saved. Your preview remains visible; try again when the API is available.");
      } finally {
        setSaving(false);
      }
    }, 500);
    return () => window.clearTimeout(timeout);
  }, [weights]);

  const displayedScore = useMemo(() => {
    if (!index || !weights) return undefined;
    const total = domains.reduce((sum, domain) => sum + weights[domain], 0);
    return domains.reduce(
      (sum, domain) => sum + index.domain_scores[domain] * weights[domain],
      0,
    ) / total;
  }, [index, weights]);

  function changeWeight(domain: IndexDomain, value: number) {
    if (!weights) return;
    hasUserChange.current = true;
    setWeights(rebalanceWeights(weights, domain, value));
  }

  if (loading) {
    return (
      <section className="mt-14 animate-pulse rounded-3xl border border-white/10 bg-slate-900/50 p-8" aria-label="Loading Planetary Health Index">
        <div className="h-4 w-48 rounded bg-slate-700" />
        <div className="mt-8 h-20 w-32 rounded bg-slate-700" />
        <div className="mt-8 h-3 w-full rounded bg-slate-800" />
      </section>
    );
  }

  if (!index || !weights || displayedScore === undefined) {
    return (
      <section role="alert" className="mt-14 rounded-3xl border border-rose-400/20 bg-rose-400/[0.06] p-8 text-rose-200">
        <h2 className="text-lg font-semibold">Planetary Health Index unavailable</h2>
        <p className="mt-2 text-sm text-rose-200/70">{error}</p>
      </section>
    );
  }

  const color = scoreColor(displayedScore);

  return (
    <section className="mt-14 overflow-hidden rounded-3xl border border-emerald-300/20 bg-slate-900/65 shadow-2xl shadow-emerald-950/20">
      <div className="grid lg:grid-cols-[0.9fr_1.1fr]">
        <div className="border-b border-white/10 bg-gradient-to-br from-emerald-400/10 to-transparent p-8 sm:p-10 lg:border-b-0 lg:border-r">
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-emerald-300">Composite signal</p>
          <h2 className="mt-4 text-2xl font-semibold text-white">Planetary Health Index</h2>
          <div className="mt-8 flex items-end gap-3">
            <span className="text-7xl font-semibold tracking-tighter text-white">{displayedScore.toFixed(1)}</span>
            <span className="mb-2 text-sm text-slate-500">/ 100</span>
          </div>
          <div className="mt-8 h-3 overflow-hidden rounded-full bg-slate-800" aria-label={`Planetary Health Index score ${displayedScore.toFixed(1)} out of 100`}>
            <div className="h-full rounded-full transition-all duration-300" style={{ width: `${displayedScore}%`, backgroundColor: color }} />
          </div>
          <p className="mt-5 text-sm leading-6 text-slate-400">
            A weighted snapshot of the latest energy, minerals, emissions, and freshwater indicators. Adjust the balance to explore different priorities.
          </p>
        </div>

        <div className="p-8 sm:p-10">
          <div className="flex items-center justify-between gap-4">
            <h3 className="text-sm font-semibold text-white">Domain weights</h3>
            <span className="text-xs text-slate-500" aria-live="polite">{saving ? "Saving…" : "Saved"}</span>
          </div>
          <div className="mt-7 space-y-7">
            {domains.map((domain) => {
              const meta = domainMeta[domain];
              return (
                <div key={domain}>
                  <div className="mb-3 flex items-center justify-between">
                    <label htmlFor={`${domain}-weight`} className={`text-sm font-medium ${meta.text}`}>{meta.label}</label>
                    <span className="text-sm tabular-nums text-slate-300">{Math.round(weights[domain] * 100)}%</span>
                  </div>
                  <input
                    id={`${domain}-weight`}
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={weights[domain]}
                    onChange={(event) => changeWeight(domain, Number(event.target.value))}
                    className="h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-700"
                    style={{ accentColor: meta.color }}
                  />
                  <div className="mt-2 flex justify-between text-xs text-slate-500">
                    <span>Domain score</span>
                    <span>{index.domain_scores[domain].toFixed(1)} / 100</span>
                  </div>
                </div>
              );
            })}
          </div>
          {error && <p role="alert" className="mt-6 text-sm text-rose-300">{error}</p>}
        </div>
      </div>
    </section>
  );
}
