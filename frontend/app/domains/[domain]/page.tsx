import { notFound } from "next/navigation";

import { DomainDashboard } from "../../../components/domain-dashboard";
import type { Domain } from "../../../lib/api";

const domains: Domain[] = ["energy", "minerals", "emissions"];

export function generateStaticParams() {
  return domains.map((domain) => ({ domain }));
}

export default function DomainPage({ params }: { params: { domain: string } }) {
  if (!domains.includes(params.domain as Domain)) notFound();
  return <DomainDashboard domain={params.domain as Domain} />;
}
