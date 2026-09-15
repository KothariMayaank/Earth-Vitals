import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";


export const metadata: Metadata = {
  title: "Earth Vitals",
  description: "Tracking the planet's vital signs.",
};


export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">
          <header className="border-b border-white/10 bg-slate-950/80 backdrop-blur-xl">
            <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5 lg:px-8">
              <Link href="/" className="group flex items-center gap-3" aria-label="Earth Vitals home">
                <span className="grid h-9 w-9 place-items-center rounded-full border border-emerald-300/30 bg-emerald-400/10 text-lg text-emerald-300 transition group-hover:bg-emerald-400/20">
                  ◉
                </span>
                <span>
                  <span className="block text-sm font-semibold tracking-[0.18em] text-white">EARTH VITALS</span>
                  <span className="block text-[10px] uppercase tracking-[0.2em] text-slate-500">Planetary data monitor</span>
                </span>
              </Link>
              <nav className="hidden items-center gap-6 text-sm text-slate-400 sm:flex" aria-label="Domain navigation">
                <Link className="transition hover:text-amber-300" href="/domains/energy">Energy</Link>
                <Link className="transition hover:text-stone-200" href="/domains/minerals">Minerals</Link>
                <Link className="transition hover:text-sky-300" href="/domains/emissions">Emissions</Link>
              </nav>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
