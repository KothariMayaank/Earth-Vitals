export type Domain = "energy" | "minerals" | "emissions";

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

export type IndexValues = Record<Domain, number>;

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
