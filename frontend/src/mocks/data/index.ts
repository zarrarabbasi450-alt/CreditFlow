import type {
  AuthSession,
  AuthUser,
  BillingOverview,
  ContentItem,
  CreditsOverview,
  ProductView,
  Role,
  Schedule,
  ScraperJob,
  ServiceHealth,
  UsageSummary,
  User,
} from "@/types";
export const chart = [
  { day: "Mon", tokens: 12400, posts: 8 },
  { day: "Tue", tokens: 18100, posts: 12 },
  { day: "Wed", tokens: 15600, posts: 9 },
  { day: "Thu", tokens: 24300, posts: 16 },
  { day: "Fri", tokens: 21900, posts: 14 },
  { day: "Sat", tokens: 9800, posts: 5 },
  { day: "Sun", tokens: 14200, posts: 7 },
];
const activity = [
  {
    title: "LinkedIn campaign published",
    detail: "Product intelligence launch · 2m ago",
    status: "Published",
  },
  { title: "Competitive brief generated", detail: "Claude 3.7 Sonnet · 18m ago", status: "Complete" },
  { title: "Pricing page scraped", detail: "64 insights captured · 1h ago", status: "Complete" },
  { title: "Weekly thought leadership", detail: "Next run Jul 18, 9:30 AM", status: "Scheduled" },
];
const metrics = [
  { label: "Available credits", value: "12,480", change: "+8.2%" },
  { label: "Content generated", value: "386", change: "+24%" },
  { label: "Scheduled posts", value: "42", change: "11 this week" },
  { label: "Success rate", value: "98.7%", change: "+1.4%" },
];
export const productViews: Record<string, ProductView> = {
  dashboard: {
    title: "Good morning, Avery",
    eyebrow: "Tuesday, July 15",
    description:
      "Your content engine is healthy. Three campaigns are ready for review and 11 posts are scheduled this week.",
    action: "Create content",
    metrics,
    rows: activity,
    chart,
  },
  "ai-studio": {
    title: "AI generation studio",
    eyebrow: "Create",
    description:
      "Generate on-brand content with model controls, streaming output, and complete usage visibility.",
    action: "New generation",
  },
  content: {
    title: "Content library",
    eyebrow: "Content",
    description:
      "Organize drafts, approvals, versions, tags, and publishing-ready assets across your workspace.",
    action: "New content",
    rows: [
      {
        title: "The operating system for modern content teams",
        detail: "LinkedIn post · Avery Moore",
        status: "Approved",
      },
      { title: "Q3 product intelligence campaign", detail: "Campaign brief · Nina Patel", status: "Draft" },
      { title: "Why predictable publishing compounds", detail: "Article · Leo Schmidt", status: "Review" },
      {
        title: "AI workflow benchmark report",
        detail: "LinkedIn carousel · Avery Moore",
        status: "Scheduled",
      },
    ],
  },
  scheduler: {
    title: "Publishing schedule",
    eyebrow: "Automations",
    description: "Coordinate one-time and recurring content across channels and timezones.",
    action: "Schedule content",
    rows: [
      { title: "Weekly founder perspective", detail: "Every Tuesday · 9:30 AM PKT", status: "Recurring" },
      { title: "Q3 launch announcement", detail: "Jul 18 · 11:00 AM PKT", status: "Scheduled" },
      {
        title: "Product insights roundup",
        detail: "First weekday monthly · 10:00 AM PKT",
        status: "Recurring",
      },
    ],
  },
  publishing: {
    title: "Social publishing",
    eyebrow: "LinkedIn",
    description: "Connect company pages, publish text and images, and monitor provider delivery responses.",
    action: "Create post",
    rows: [
      { title: "Orion Media Group", detail: "Connected as organization page", status: "Connected" },
      ...activity.slice(0, 3),
    ],
  },
  scraper: {
    title: "Research scraper",
    eyebrow: "Intelligence",
    description:
      "Queue compliant web research jobs and turn source material into structured content insights.",
    action: "New scrape",
    rows: [
      { title: "Acme pricing intelligence", detail: "12 pages · 64 insights", status: "Complete" },
      { title: "AI workflow benchmark", detail: "8 of 14 pages processed", status: "Running" },
      { title: "Creator economy signals", detail: "Scheduled for 2:00 AM", status: "Queued" },
    ],
  },
  usage: {
    title: "Usage & metering",
    eyebrow: "This billing cycle",
    description: "Understand token volume, model cost, quotas, and the teams driving content output.",
    action: "Export report",
    metrics: [
      { label: "Tokens used", value: "116.3K", change: "68% of quota" },
      { label: "Model cost", value: "$184.20", change: "−6.4% per output" },
      { label: "Generations", value: "386", change: "+24%" },
      { label: "Quota remaining", value: "53.7K", change: "16 days left" },
    ],
    chart,
  },
  credits: {
    title: "Credits",
    eyebrow: "Balance & marketplace",
    description: "Review the append-only ledger, manage your balance, and securely trade unused credits.",
    action: "Buy credits",
    metrics: [
      { label: "Available", value: "12,480", change: "Current balance" },
      { label: "Monthly grant", value: "15,000", change: "Renews Aug 1" },
      { label: "Used this month", value: "4,920", change: "−12% vs June" },
      { label: "Marketplace value", value: "$624", change: "Estimated" },
    ],
    rows: [
      { title: "Monthly Pro grant", detail: "Jul 1, 2026", status: "Grant", amount: "+15,000" },
      { title: "AI generation · 2,840 tokens", detail: "Jul 14, 2026", status: "Usage", amount: "−284" },
      { title: "Marketplace sale", detail: "Jul 13, 2026", status: "Trade", amount: "+1,200" },
      { title: "LinkedIn image campaign", detail: "Jul 12, 2026", status: "Usage", amount: "−46" },
    ],
  },
  billing: {
    title: "Billing & subscription",
    eyebrow: "Pro plan",
    description: "Manage your subscription, invoices, payment methods, and billing contacts.",
    action: "Manage plan",
    metrics: [
      { label: "Current plan", value: "Pro", change: "12 seats" },
      { label: "Next invoice", value: "$299", change: "Due Aug 1" },
      { label: "Payment method", value: "•••• 4242", change: "Visa · expires 08/28" },
      { label: "Billing status", value: "Active", change: "No action required" },
    ],
    rows: [
      { title: "Invoice CF-2026-071", detail: "Jul 1, 2026 · Visa •••• 4242", status: "$299 · Paid" },
      { title: "Invoice CF-2026-061", detail: "Jun 1, 2026 · Visa •••• 4242", status: "$299 · Paid" },
    ],
  },
  team: {
    title: "Team & access",
    eyebrow: "Orion Media Group",
    description: "Invite collaborators and manage Owner, Admin, and Member permissions.",
    action: "Invite member",
    rows: [
      { title: "Avery Moore", detail: "owner@orionmedia.com", status: "Owner · Active" },
      { title: "Nina Patel", detail: "admin@orionmedia.com", status: "Admin · Active" },
      { title: "Leo Schmidt", detail: "member@orionmedia.com", status: "Member · Active" },
      { title: "Maya Brooks", detail: "maya@orionmedia.com", status: "Member · Invited" },
    ],
  },
  notifications: {
    title: "Notification center",
    eyebrow: "3 recent updates",
    description:
      "Stay ahead of publishing results, balance thresholds, job completions, and account activity.",
    action: "Mark all read",
    rows: [
      {
        title: "Campaign published successfully",
        detail: "The Q3 launch post is now live on LinkedIn.",
        status: "Unread",
      },
      {
        title: "Credit threshold reached",
        detail: "Your workspace has used 80% of its monthly grant.",
        status: "Unread",
      },
      { title: "Scrape completed", detail: "64 insights were captured from 12 pages.", status: "Read" },
    ],
  },
  settings: {
    title: "Workspace settings",
    eyebrow: "Account",
    description:
      "Manage profile details, organization preferences, active sessions, API keys, and notification rules.",
    action: "Save changes",
    rows: [
      {
        title: "Organization profile",
        detail: "Name, locale, timezone and brand defaults",
        status: "Configured",
      },
      { title: "Active sessions", detail: "3 trusted devices · last activity now", status: "Review" },
      { title: "API keys", detail: "2 active keys · latest used 4m ago", status: "Manage" },
      { title: "Notification preferences", detail: "Email and in-app delivery rules", status: "Configured" },
    ],
  },
  admin: {
    title: "Platform operations",
    eyebrow: "SuperAdmin",
    description:
      "Monitor service health, tenant access, audit events, failed jobs, and feature rollout controls.",
    action: "Platform search",
    metrics: [
      { label: "Active accounts", value: "1,284", change: "+36 this month" },
      { label: "Active users", value: "8,942", change: "+12.8%" },
      { label: "Platform uptime", value: "99.98%", change: "Last 30 days" },
      { label: "Failed jobs", value: "3", change: "Needs review" },
    ],
    rows: [
      { title: "API Gateway", detail: "99.99% uptime · 42ms p95", status: "Healthy" },
      { title: "AI Generation", detail: "99.95% uptime · 3 active jobs", status: "Healthy" },
      { title: "Social Publishing", detail: "1 retry pending · 182ms p95", status: "Degraded" },
      { title: "Scheduler", detail: "42 jobs queued · workers current", status: "Healthy" },
    ],
  },
};
const permissions: Record<Role, AuthUser["permissions"]> = {
  Owner: ["workspace:read", "workspace:manage", "billing:read", "billing:manage", "content:write"],
  Admin: ["workspace:read", "workspace:manage", "billing:read", "content:write"],
  Member: ["workspace:read", "content:write"],
  SuperAdmin: ["workspace:read", "admin:read", "admin:manage"],
};
export const credentials = [
  { email: "owner@orionmedia.com", password: "Password123!", name: "Avery Moore", role: "Owner" },
  { email: "admin@orionmedia.com", password: "Password123!", name: "Nina Patel", role: "Admin" },
  { email: "member@orionmedia.com", password: "Password123!", name: "Leo Schmidt", role: "Member" },
  { email: "superadmin@creditflow.com", password: "Password123!", name: "Riley Chen", role: "SuperAdmin" },
] as const;
export function sessionFor(role: Role, name: string, email: string): AuthSession {
  return {
    user: {
      id: `user_${role.toLowerCase()}`,
      name,
      email,
      role,
      permissions: permissions[role],
      tenant: {
        id: role === "SuperAdmin" ? "platform" : "tenant_orion",
        name: role === "SuperAdmin" ? "CreditFlow Platform" : "Orion Media Group",
        slug: role === "SuperAdmin" ? "platform" : "orion-media",
      },
      workspace: {
        id: role === "SuperAdmin" ? "platform" : "workspace_orion",
        tenantId: role === "SuperAdmin" ? "platform" : "tenant_orion",
        name: role === "SuperAdmin" ? "CreditFlow Platform" : "Orion Media Group",
        plan: role === "SuperAdmin" ? "Platform" : "Pro",
      },
    },
    tokens: { accessToken: `mock_access_${role}`, refreshToken: `mock_refresh_${role}`, expiresIn: 900 },
  };
}
export const users: User[] = credentials.map((item, index) => ({
  id: `user_${index + 1}`,
  accountId: "tenant_orion",
  name: item.name,
  email: item.email,
  role: item.role,
  status: "Active",
}));
export const contentItems: ContentItem[] = productViews.content.rows!.map((row, index) => ({
  id: `content_${index + 1}`,
  accountId: "tenant_orion",
  createdBy: "user_1",
  title: row.title,
  body: `Draft body for ${row.title}.`,
  contentType: (["post", "campaign_brief", "article", "carousel"] as const)[index] ?? "post",
  owner: row.detail.split(" · ")[1],
  status:
    row.status === "Approved"
      ? "approved"
      : row.status === "Published" || row.status === "Scheduled"
        ? "published"
        : "draft",
  tags: ["campaign"],
  imageUrl: null,
  imageAssetRef: null,
  sourceGenerationId: null,
  createdAt: "2026-07-15T10:00:00Z",
  updatedAt: "2026-07-15T10:00:00Z",
  publishedAt: row.status === "Scheduled" ? "2026-07-16T10:00:00Z" : null,
  version: index + 1,
}));
export const schedules: Schedule[] = [
  {
    id: "schedule_1",
    accountId: "tenant_orion",
    title: "Weekly founder perspective",
    status: "Recurring",
    publishAt: "2026-07-21T09:30:00+05:00",
    timezone: "Asia/Karachi",
    recurrence: { frequency: "weekly", nextRunAt: "2026-07-21T09:30:00+05:00" },
  },
];
export const scraperJobs: ScraperJob[] = [
  {
    id: "scrape_1",
    accountId: "tenant_orion",
    url: "https://example.com/pricing",
    name: "Acme pricing intelligence",
    status: "Complete",
    pagesProcessed: 12,
    insightCount: 64,
    createdAt: "2026-07-14T08:00:00Z",
  },
];
export const serviceHealth: ServiceHealth[] = productViews.admin.rows!.map((row) => ({
  service: row.title,
  status: row.status as ServiceHealth["status"],
  uptime: 99.95,
  latencyP95Ms: 42,
  detail: row.detail,
}));
export const billing: BillingOverview = {
  view: productViews.billing,
  subscription: {
    id: "sub_pro",
    accountId: "tenant_orion",
    plan: "Pro",
    status: "Active",
    seats: 12,
    amountCents: 29900,
    currency: "USD",
    renewsAt: "2026-08-01",
  },
  invoices: [],
  paymentMethods: [
    { id: "pm_1", brand: "Visa", last4: "4242", expiresMonth: 8, expiresYear: 2028, isDefault: true },
  ],
};
export const credits: CreditsOverview = {
  view: productViews.credits,
  balance: 12480,
  ledger: [],
  listings: [],
};
export const usage: UsageSummary = {
  accountId: "tenant_orion",
  periodStart: "2026-07-01",
  periodEnd: "2026-07-31",
  tokensUsed: 116300,
  costMicrousd: 184200000,
  quotaTokens: 170000,
  remainingTokens: 53700,
  quotaPercentage: 68.41,
  generations: 386,
  byModel: [{ model: "gpt-4.1", tokens: 116300, costMicrousd: 184200000, generations: 386 }],
  metrics: productViews.usage.metrics!,
  daily: chart,
  view: productViews.usage,
};
