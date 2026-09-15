import { DomainScoreCards } from "../components/domain-score-cards";
import { PlanetaryHealthIndex } from "../components/planetary-index";
import { WorldOverviewMap } from "../components/world-overview-map";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-7xl px-6 py-12 lg:px-8 lg:py-16">
      <div className="max-w-4xl">
        <p className="mb-4 text-xs font-semibold uppercase tracking-[0.28em] text-emerald-300">Planetary overview</p>
        <h1 className="text-balance text-4xl font-semibold tracking-tight text-white sm:text-5xl">
          Earth&apos;s vital signs, in one view.
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-slate-400 sm:text-lg">
          A transparent snapshot of global energy, natural resources, and atmospheric health—built from the latest available observations.
        </p>
      </div>

      <PlanetaryHealthIndex />
      <WorldOverviewMap />
      <DomainScoreCards />
    </main>
  );
}
