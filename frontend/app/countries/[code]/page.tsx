import { CountryDashboard } from "../../../components/country-dashboard";


export default function CountryPage({
  params,
  searchParams,
}: {
  params: { code: string };
  searchParams?: { domain?: string };
}) {
  const initialDomain = searchParams?.domain === "freshwater" ? "freshwater" : "energy";
  return <CountryDashboard code={params.code.toUpperCase()} initialDomain={initialDomain} />;
}
