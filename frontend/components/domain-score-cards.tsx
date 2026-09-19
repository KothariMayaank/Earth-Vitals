"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { type Domain, type IndexDomain, type PlanetaryIndex, fetchPlanetaryIndex } from "../lib/api";


const domains: Array<{
  key: Domain;
  scoreKey?: IndexDomain;
  name: string;
  href: string;
  description: string;
  accent: string;
  text: string;
  bar: string;
}> = [
  {
    key: "energy",
    scoreKey: "energy",
    name: "Energy",
    href: "/domains/energy",
    description: "Electricity generation and the transition to renewable power.",
    accent: "border-amber-400/25 hover:border-amber-300/60 hover:bg-amber-400/[0.05]",
    text: "text-amber-300",
    bar: "bg-amber-300",
  },
  {
    key: "minerals",
    scoreKey: "minerals",
    name: "Minerals",
    href: "/domains/minerals",
    description: "Finite reserves supporting infrastructure and electrification.",
    accent: "border-stone-400/25 hover:border-stone-200/60 hover:bg-stone-300/[0.05]",
    text: "text-stone-300",
    bar: "bg-stone-300",
  },
  {
    key: "emissions",
    scoreKey: "emissions",
    name: "Emissions",
    href: "/domains/emissions",
    description: "Atmospheric health through globally aggregated air-quality signals.",
    accent: "border-sky-400/25 hover:border-sky-300/60 hover:bg-sky-400/[0.05]",
    text: "text-sky-300",
    bar: "bg-sky-300",
  },
  {
    key: "freshwater",
    name: "Freshwater",
    href: "/domains/freshwater",
    description: "Water availability, withdrawal pressure, stress, and safe drinking-water access.",
    accent: "border-cyan-400/25 hover:border-cyan-300/60 hover:bg-cyan-400/[0.05]",
    text: "text-cyan-300",
    bar: "bg-cyan-300",
  },
];


export function DomainScoreCards() {
  const [index, setIndex] = useState<PlanetaryIndex>();
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    fetchPlanetaryIndex()
      .then((result) => active && setIndex(result))
      .catch(() => active && setError(true));
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="mt-14" aria-labelledby="domain-scores-heading">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Explore the system</p>
          <h2 id="domain-scores-heading" className="mt-2 text-2xl font-semibold text-white">Earth system domains</h2>
        </div>
        <p className="max-w-lg text-sm leading-6 text-slate-500">Open a domain to inspect its latest metrics, source context, and historical series.</p>
      </div>

      {error && (
        <p role="alert" className="mb-5 rounded-xl border border-rose-400/20 bg-rose-400/[0.06] px-5 py-4 text-sm text-rose-200">
          Current domain scores are unavailable, but the domain pages can still be opened.
        </p>
      )}

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        {domains.map((domain, position) => {
          const score = domain.scoreKey ? index?.domain_scores[domain.scoreKey] : undefined;
          return (
            <Link
              key={domain.key}
              href={domain.href}
              className={`group rounded-2xl border bg-slate-900/55 p-7 shadow-xl shadow-black/10 transition duration-300 ${domain.accent}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className={`text-xs font-semibold uppercase tracking-[0.2em] ${domain.text}`}>
                  0{position + 1} / Domain
                </div>
                <span className="text-sm text-slate-500 transition-transform group-hover:translate-x-1">→</span>
              </div>
              <h3 className="mt-7 text-2xl font-semibold text-white">{domain.name}</h3>
              <div className="mt-5 flex items-end gap-2">
                {!domain.scoreKey ? (
                  <span className="text-sm font-medium text-cyan-200">Observational</span>
                ) : score === undefined ? (
                  <span className="h-10 w-24 animate-pulse rounded bg-slate-800" aria-label="Loading score" />
                ) : (
                  <>
                    <span className="text-4xl font-semibold tracking-tight text-white">{score.toFixed(1)}</span>
                    <span className="mb-1 text-xs text-slate-500">/ 100</span>
                  </>
                )}
              </div>
              <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-800">
                {score !== undefined && <div className={`h-full rounded-full ${domain.bar}`} style={{ width: `${score}%` }} />}
              </div>
              <p className="mt-5 min-h-16 text-sm leading-6 text-slate-400">{domain.description}</p>
              <span className="mt-5 inline-block text-sm font-medium text-slate-200">Explore {domain.name.toLowerCase()}</span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
