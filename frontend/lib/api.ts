export type Domain = "energy" | "minerals" | "emissions" | "freshwater";
export type IndexDomain = Exclude<Domain, "freshwater">;

export type DomainMetric = {
  id: number;
  key: string;
  display_name: string;
  domain: Domain;
  unit: string;
  cadence: string;
  timestamp: string;
  value: number;
  description: string | null;
  source_name: string;
  source_url: string;
};

export type HistoryPoint = {
  timestamp: string;
  value: number;
};

export type IndexValues = Record<IndexDomain, number>;

export type PlanetaryIndex = {
  composite_score: number;
  domain_scores: IndexValues;
  weights: IndexValues;
};

export type ProjectionPoint = {
  year: number;
  value: number;
};

export type MetricProjection = {
  projection_id: number;
  metric_key: string;
  projection_type: "finite_resource" | "trend";
  scenario_label: string;
  assumption_pct_change_per_year: number;
  baseline_year: number;
  baseline_value: number;
  baseline_extraction_rate: number | null;
  target_year: number | null;
  projected_value: number | null;
  projected_depletion_year: number | null;
  beyond_modeled_horizon: boolean;
  unit: string;
  series: ProjectionPoint[];
  result_summary: string;
  methodology_note: string;
  computed_at: string;
};

export type MetricMapPoint = {
  code: string;
  name: string;
  timestamp: string;
  value: number;
};

export type MetricMap = {
  metric_key: string;
  display_name: string;
  unit: string;
  points: MetricMapPoint[];
};

export type Geography = {
  id: number;
  code: string;
  name: string;
  type: "global" | "region" | "country";
};

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

async function putJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function fetchDomainSummary(domain: Domain): Promise<DomainMetric[]> {
  return getJson<DomainMetric[]>(`/domains/${domain}/summary`);
}

export function fetchMetricHistory(metricKey: string): Promise<HistoryPoint[]> {
  return getJson<HistoryPoint[]>(`/metrics/${encodeURIComponent(metricKey)}/history`);
}

export function fetchMetricMap(metricKey: string): Promise<MetricMap> {
  return getJson<MetricMap>(`/metrics/${encodeURIComponent(metricKey)}/map`);
}

export function fetchCountrySummary(countryCode: string): Promise<DomainMetric[]> {
  return getJson<DomainMetric[]>(`/countries/${encodeURIComponent(countryCode)}/summary`);
}

export function fetchCountry(countryCode: string): Promise<Geography> {
  return getJson<Geography>(`/countries/${encodeURIComponent(countryCode)}`);
}

export function fetchCountryMetricHistory(
  countryCode: string,
  metricKey: string,
): Promise<HistoryPoint[]> {
  return getJson<HistoryPoint[]>(
    `/countries/${encodeURIComponent(countryCode)}/metrics/${encodeURIComponent(metricKey)}/history`,
  );
}

export function fetchPlanetaryIndex(): Promise<PlanetaryIndex> {
  return getJson<PlanetaryIndex>("/index/current");
}

export function updateIndexWeights(weights: IndexValues): Promise<PlanetaryIndex> {
  return putJson<PlanetaryIndex>("/index/weights", weights);
}

export function createMetricProjection(
  metricKey: string,
  rateOfChangePct: number,
  targetYear?: number,
): Promise<MetricProjection> {
  return postJson<MetricProjection>(`/projections/${encodeURIComponent(metricKey)}`, {
    rate_of_change_pct: rateOfChangePct,
    ...(targetYear === undefined ? {} : { target_year: targetYear }),
  });
}
