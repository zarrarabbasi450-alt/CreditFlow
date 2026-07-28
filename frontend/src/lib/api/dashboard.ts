import { getCredits } from "./credits";
import { getCurrentAccount, listAccountMembers } from "./tenants";
import { getUsage } from "./usage";
import type { ProductView } from "@/types";

const integer = new Intl.NumberFormat("en-US");

export const getDashboard = async (): Promise<ProductView> => {
  const account = await getCurrentAccount();
  const [usageResult, creditsResult, membersResult] = await Promise.allSettled([
    getUsage(),
    getCredits(),
    listAccountMembers(account.id),
  ]);

  const degraded: string[] = [];
  const rows: ProductView["rows"] = [];

  const teamSize = membersResult.status === "fulfilled" ? membersResult.value.length : null;
  if (membersResult.status === "rejected") degraded.push("team");

  let creditBalance: number | null = null;
  if (creditsResult.status === "fulfilled") {
    creditBalance = creditsResult.value.balance;
    for (const entry of creditsResult.value.ledger.slice(0, 3)) {
      rows?.push({
        title: entry.description,
        detail: `${entry.type} · ${new Date(entry.createdAt).toLocaleDateString()}`,
        status: entry.amount > 0 ? `+${integer.format(entry.amount)}` : integer.format(entry.amount),
      });
    }
  } else {
    degraded.push("credits");
  }

  let tokensUsed: number | null = null;
  let quotaPercentage: number | null = null;
  if (usageResult.status === "fulfilled") {
    tokensUsed = usageResult.value.tokensUsed;
    quotaPercentage = usageResult.value.quotaPercentage;
  } else {
    degraded.push("usage");
  }

  return {
    title: `${account.name} overview`,
    eyebrow: "Owner dashboard",
    description: degraded.length
      ? `Account-wide summary — ${degraded.join(", ")} data is temporarily unavailable.`
      : "Account-wide summary of usage, credits, team size, and plan tier.",
    action: "Create post",
    metrics: [
      { label: "Plan tier", value: account.plan_tier, change: `${account.seat_count} seat(s) purchased` },
      { label: "Team size", value: teamSize === null ? "—" : integer.format(teamSize), change: "Active members" },
      {
        label: "Credit balance",
        value: creditBalance === null ? "—" : integer.format(creditBalance),
        change: "Available now",
      },
      {
        label: "Tokens used",
        value: tokensUsed === null ? "—" : integer.format(tokensUsed),
        change: quotaPercentage === null ? "This period" : `${quotaPercentage}% of quota`,
      },
    ],
    rows,
  };
};
