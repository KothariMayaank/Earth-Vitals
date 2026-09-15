"use client";

import {
  ComposableMap,
  Geographies,
  Geography,
  Graticule,
  Sphere,
} from "react-simple-maps";
import worldGeography from "world-atlas/countries-110m.json";


export function WorldOverviewMap() {
  return (
    <section className="mt-8 overflow-hidden rounded-3xl border border-white/10 bg-slate-900/45 shadow-2xl shadow-black/10">
      <div className="flex flex-col gap-5 border-b border-white/10 px-7 py-7 sm:flex-row sm:items-end sm:justify-between sm:px-10">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-300">
            Global context
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-white">One planet, shared signals</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            Earth Vitals currently tracks worldwide aggregates. Every country is shown uniformly because no country-level values are encoded yet.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2 rounded-full border border-sky-300/20 bg-sky-400/[0.06] px-3 py-1.5 text-xs text-sky-200">
          <span className="h-2 w-2 rounded-full bg-sky-300" />
          Illustrative global view
        </div>
      </div>

      <div className="relative bg-[radial-gradient(circle_at_center,rgba(14,165,233,0.10),transparent_55%)] px-3 py-4 sm:px-8">
        <div className="pointer-events-none absolute inset-x-[20%] top-[18%] h-1/2 rounded-full bg-sky-400/[0.04] blur-3xl" />
        <ComposableMap
          projection="geoEqualEarth"
          projectionConfig={{ scale: 150 }}
          width={800}
          height={390}
          role="img"
          aria-label="Illustrative world map. Countries have uniform styling because Earth Vitals currently contains global-average data only."
          className="relative mx-auto h-auto w-full max-w-5xl"
        >
          <Sphere id="earth-vitals-sphere" fill="#071426" stroke="#1e3a52" strokeWidth={0.8} />
          <Graticule fill="transparent" stroke="#1e3a52" strokeWidth={0.45} />
          <Geographies geography={worldGeography}>
            {({ geographies }) =>
              geographies.map((geography) => (
                <Geography
                  key={geography.rsmKey}
                  geography={geography}
                  fill="#174564"
                  stroke="#071827"
                  strokeWidth={0.55}
                  tabIndex={-1}
                  style={{
                    default: { outline: "none" },
                    hover: { fill: "#1d567b", outline: "none" },
                    pressed: { fill: "#1d567b", outline: "none" },
                  }}
                />
              ))
            }
          </Geographies>
        </ComposableMap>
      </div>

      <div className="border-t border-white/10 px-7 py-4 text-xs leading-5 text-slate-500 sm:px-10">
        Map treatment is illustrative—not a country ranking, heat map, or geographic comparison.
      </div>
    </section>
  );
}
