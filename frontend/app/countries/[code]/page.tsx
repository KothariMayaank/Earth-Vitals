import { CountryDashboard } from "../../../components/country-dashboard";


export default function CountryPage({ params }: { params: { code: string } }) {
  return <CountryDashboard code={params.code.toUpperCase()} />;
}
