import { notFound } from "next/navigation";
import { ProductPage } from "@/features/product/product-page";
const sections = new Set([
  "dashboard",
  "ai-studio",
  "content",
  "scheduler",
  "publishing",
  "scraper",
  "usage",
  "credits",
  "billing",
  "team",
  "notifications",
  "settings",
  "admin",
]);
export default async function WorkspacePage({
  params,
}: {
  params: Promise<{ section: string; subsection?: string[] }>;
}) {
  const { section, subsection } = await params;
  if (!sections.has(section) || (subsection?.length && subsection.length > 1)) notFound();
  return <ProductPage section={section} subsection={subsection?.[0]} />;
}
