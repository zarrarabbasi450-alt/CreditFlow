import { http, HttpResponse } from "msw";
import {
  billing,
  contentItems,
  credentials,
  credits,
  productViews,
  schedules,
  scrapedDocuments,
  scraperJobs,
  serviceHealth,
  sessionFor,
  usage,
  users,
} from "./data";
import type { ApiResponse, Role, ScraperJob } from "@/types";
const toRawScraperJob = (job: ScraperJob) => ({
  id: job.id,
  account_id: job.accountId,
  created_by: job.createdBy,
  job_type: job.jobType,
  target: job.target,
  name: job.name,
  max_pages: job.maxPages,
  status: job.status,
  recurring: job.recurring,
  interval_hours: job.intervalHours,
  next_run_at: job.nextRunAt,
  last_run_at: job.lastRunAt,
  pages_processed: job.pagesProcessed,
  answer: job.answer ?? null,
  answer_html: job.answer ? job.answer.replace(/^# (.+)$/m, "<h1>$1</h1>") : "",
  failure_reason: job.failureReason,
  attempts: job.attempts,
  created_at: job.createdAt,
  updated_at: job.updatedAt,
});
const base = "*/api/v1";
const meta = () => ({
  requestId: `req_${crypto.randomUUID()}`,
  correlationId: `corr_${crypto.randomUUID()}`,
});
const ok = <T>(data: T, status = 200) =>
  HttpResponse.json<ApiResponse<T>>({ success: true, data, meta: meta() }, { status });
let currentMockProfile: (typeof credentials)[number] | undefined;
const mockSessionResponse = (profile: (typeof credentials)[number]) => {
  const session = sessionFor(profile.role, profile.name, profile.email);
  return ok({
    user: {
      id: session.user.id,
      email: session.user.email,
      accountId: profile.role === "SuperAdmin" ? "platform" : "tenant_orion",
      role: profile.role,
      accountRole: profile.role === "SuperAdmin" ? ("Owner" as const) : profile.role,
      platformRole: profile.role === "SuperAdmin" ? ("SuperAdmin" as const) : null,
    },
    tokens: session.tokens,
  });
};
export const handlers = [
  http.get(`${base}/auth/me`, () =>
    ok({
      id: "user_owner",
      email: "owner@orionmedia.com",
      accountId: "tenant_orion",
      role: "Owner" as const,
      accountRole: "Owner" as const,
      platformRole: null,
    }),
  ),
  http.post(`${base}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    const profile = credentials.find((item) => item.email === body.email && item.password === body.password);
    if (!profile)
      return HttpResponse.json(
        {
          success: false,
          error: { code: "INVALID_CREDENTIALS", message: "Email or password is incorrect" },
          meta: meta(),
        },
        { status: 401 },
      );
    currentMockProfile = profile;
    return mockSessionResponse(profile);
  }),
  http.post(`${base}/auth/refresh`, () => {
    if (!currentMockProfile)
      return HttpResponse.json(
        { success: false, error: { code: "MISSING_REFRESH_TOKEN", message: "No active session was found" }, meta: meta() },
        { status: 401 },
      );
    return mockSessionResponse(currentMockProfile);
  }),
  http.post(`${base}/auth/switch-account`, () => mockSessionResponse(currentMockProfile ?? credentials[0])),
  http.post(`${base}/auth/logout`, () => {
    currentMockProfile = undefined;
    return ok({ message: "Logged out successfully" });
  }),
  http.post(`${base}/auth/verify-email`, () => ok({ message: "Email verified successfully" })),
  http.post(`${base}/auth/forgot-password`, () =>
    ok({ message: "If the account exists, a reset code will be sent" }),
  ),
  http.post(`${base}/auth/forgot-password/verify`, async ({ request }) => {
    const body = (await request.json()) as { code: string };
    if (body.code !== "123456")
      return HttpResponse.json(
        { success: false, error: { code: "INVALID_RESET_CODE", message: "Reset code is invalid" }, meta: meta() },
        { status: 400 },
      );
    return ok({ message: "Reset code is valid" });
  }),
  http.post(`${base}/auth/reset-password`, async ({ request }) => {
    const body = (await request.json()) as { code: string };
    if (body.code !== "123456")
      return HttpResponse.json(
        { success: false, error: { code: "INVALID_RESET_CODE", message: "Reset code is invalid" }, meta: meta() },
        { status: 400 },
      );
    return ok({ message: "Password reset successfully" });
  }),
  http.post(`${base}/auth/development-role`, async ({ request }) => {
    const { role } = (await request.json()) as { role: Role };
    const profile = credentials.find((item) => item.role === role) ?? credentials[0];
    return ok(sessionFor(profile.role, profile.name, profile.email));
  }),
  http.get(`${base}/users`, () =>
    ok({ view: productViews.team, users: { items: users, page: 1, pageSize: 20, total: users.length } }),
  ),
  http.post(`${base}/users/invitations`, async ({ request }) => {
    const body = (await request.json()) as { email: string; role: Role };
    return ok(
      {
        id: "invite_new",
        email: body.email,
        role: body.role,
        expiresAt: "2026-07-22T00:00:00Z",
        status: "Pending" as const,
      },
      201,
    );
  }),
  http.get(`${base}/tenants/current`, () =>
    ok({
      id: "tenant_orion",
      name: "Orion Media Group",
      slug: "orion-media",
      timezone: "Asia/Karachi",
      locale: "en-US",
      ownerId: "user_1",
    }),
  ),
  http.get(`${base}/tenants/current/workspace`, () =>
    ok({
      id: "workspace_orion",
      tenantId: "tenant_orion",
      name: "Orion Media Group",
      plan: "Pro",
      seatLimit: 12,
    }),
  ),
  http.get(`${base}/tenants/current/overview`, () =>
    ok({
      view: productViews.settings,
      tenant: {
        id: "tenant_orion",
        name: "Orion Media Group",
        slug: "orion-media",
        timezone: "Asia/Karachi",
        locale: "en-US",
        ownerId: "user_1",
      },
      workspace: {
        id: "workspace_orion",
        tenantId: "tenant_orion",
        name: "Orion Media Group",
        plan: "Pro",
        seatLimit: 12,
      },
    }),
  ),
  http.get(`${base}/billing/overview`, () => ok(billing)),
  http.get(`${base}/credits/overview`, () => ok(credits)),
  http.get(`${base}/usage/summary`, () =>
    ok({
      account_id: usage.accountId,
      period_start: usage.periodStart,
      period_end: usage.periodEnd,
      tokens_used: usage.tokensUsed,
      cost_microusd: usage.costMicrousd,
      quota_tokens: usage.quotaTokens,
      remaining_tokens: usage.remainingTokens,
      quota_percentage: usage.quotaPercentage,
      generations: usage.generations,
      by_model: usage.byModel.map((item) => ({
        model: item.model,
        tokens: item.tokens,
        cost_microusd: item.costMicrousd,
        generations: item.generations,
      })),
      daily: usage.daily.map((item) => ({
        day: `2026-${item.day}`,
        tokens: item.tokens,
        cost_microusd: 0,
        generations: item.posts,
      })),
    }),
  ),
  http.get(`${base}/usage/ledger`, () => ok([])),
  http.get(`${base}/content`, () => ok({ view: productViews.content, items: contentItems })),
  http.get(`${base}/ai/overview`, () => ok(productViews["ai-studio"])),
  http.delete(`${base}/ai/history/:entryId`, () => ok(undefined, 204)),
  http.post(`${base}/ai/generations`, async ({ request }) => {
    const body = (await request.json()) as { prompt: string; generate_image?: boolean };
    return ok(
      {
        job_id: "generation_mock",
        channel: "ai:generation:generation_mock",
        model: "fast",
        status: "queued",
        image_url: body.generate_image ? "https://picsum.photos/seed/generation_mock/512" : null,
      },
      201,
    );
  }),
  http.get(`${base}/ai/generations/:jobId/stream`, ({ params }) => {
    const tokens = `Turn the prompt into a crisp, credible narrative: lead with the customer tension, show the practical shift, support it with evidence, and close with one clear action.`.split(
      " ",
    );
    const encoder = new TextEncoder();
    const frame = (event: string, data: Record<string, unknown>) =>
      encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
    const stream = new ReadableStream({
      async start(controller) {
        for (const token of tokens) {
          controller.enqueue(frame("token", { job_id: params.jobId, value: `${token} ` }));
          await new Promise((resolve) => setTimeout(resolve, 15));
        }
        controller.enqueue(frame("completed", { job_id: params.jobId }));
        controller.close();
      },
    });
    return new HttpResponse(stream, {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    });
  }),
  http.get(`${base}/scheduler`, () =>
    ok({
      items: schedules.map((item) => ({
        id: item.id,
        account_id: item.accountId,
        content_id: item.contentId,
        title: item.title,
        status: item.status,
        publish_at: item.publishAt,
        publish_at_local: item.publishAtLocal,
        timezone: item.timezone,
        fired_at: item.firedAt,
        cancelled_at: item.cancelledAt,
        created_at: item.createdAt,
        updated_at: item.updatedAt,
      })),
      timezone: "Asia/Karachi",
      range_start: "2026-07-01T00:00:00Z",
      range_end: "2026-08-15T00:00:00Z",
    }),
  ),
  http.post(`${base}/scheduler`, async ({ request }) => {
    const body = (await request.json()) as { content_id: string; title: string; publish_at: string; timezone: string };
    return ok(
      {
        id: "schedule_new",
        account_id: "tenant_orion",
        content_id: body.content_id,
        title: body.title,
        status: "scheduled" as const,
        publish_at: body.publish_at,
        publish_at_local: body.publish_at,
        timezone: body.timezone,
        fired_at: null,
        cancelled_at: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      201,
    );
  }),
  http.get(`${base}/scheduler/summary`, () =>
    ok({ scheduled_count: schedules.length, due_count: 0, next_publish_at: schedules[0]?.publishAt ?? null }),
  ),
  http.patch(`${base}/scheduler/:scheduleId`, async ({ params, request }) => {
    const body = (await request.json()) as { publish_at: string; timezone: string };
    return ok({
      id: String(params.scheduleId),
      account_id: "tenant_orion",
      content_id: "content_1",
      title: "Weekly founder perspective",
      status: "scheduled" as const,
      publish_at: body.publish_at,
      publish_at_local: body.publish_at,
      timezone: body.timezone,
      fired_at: null,
      cancelled_at: null,
      created_at: "2026-07-15T10:00:00Z",
      updated_at: new Date().toISOString(),
    });
  }),
  http.delete(`${base}/scheduler/:scheduleId`, ({ params }) =>
    ok({
      id: String(params.scheduleId),
      account_id: "tenant_orion",
      content_id: "content_1",
      title: "Weekly founder perspective",
      status: "cancelled" as const,
      publish_at: "2026-07-21T04:30:00Z",
      publish_at_local: "2026-07-21T09:30:00+05:00",
      timezone: "Asia/Karachi",
      fired_at: null,
      cancelled_at: new Date().toISOString(),
      created_at: "2026-07-15T10:00:00Z",
      updated_at: new Date().toISOString(),
    }),
  ),
  http.get(`${base}/publishing`, () =>
    ok({
      view: productViews.publishing,
      connections: [
        {
          id: "linkedin_orion",
          account_id: "tenant_orion",
          provider: "linkedin" as const,
          profile_name: "Orion Media Group",
          profile_urn: "dev:https://linkedin.com/company/orion-media",
          status: "connected" as const,
          connected_at: "2026-01-12T00:00:00Z",
        },
      ],
      jobs: [
        {
          id: "publish_mock",
          account_id: "tenant_orion",
          content_id: "content_1",
          scheduled_post_id: null,
          connection_id: "linkedin_orion",
          status: "published" as const,
          caption: "LinkedIn campaign published",
          image_url: null,
          linkedin_post_id: "dev-linkedin-publish_mock",
          linkedin_post_url: "https://linkedin.com/company/orion-media",
          failure_reason: null,
          attempts: 1,
          created_at: "2026-07-15T10:00:00Z",
          published_at: "2026-07-15T10:00:02Z",
        },
      ],
    }),
  ),
  http.post(`${base}/publishing/linkedin/connect`, () =>
    ok({ authorization_url: "https://www.linkedin.com/oauth/v2/authorization?mock=true", state: "state_mock" }),
  ),
  http.post(`${base}/publishing/linkedin/dev-connect`, async ({ request }) => {
    const body = (await request.json()) as { profile_name: string; profile_url: string };
    return ok({
      id: "linkedin_dev",
      account_id: "tenant_orion",
      provider: "linkedin" as const,
      profile_name: body.profile_name,
      profile_urn: `dev:${body.profile_url}`,
      status: "connected" as const,
      connected_at: new Date().toISOString(),
    });
  }),
  http.delete(`${base}/publishing/connections/:connectionId`, () => ok({ message: "LinkedIn connection revoked" })),
  http.post(`${base}/publishing/linkedin`, () =>
    ok(
      {
        id: "publication_new",
        account_id: "tenant_orion",
        content_id: "00000000-0000-0000-0000-000000000000",
        scheduled_post_id: null,
        connection_id: "linkedin_orion",
        status: "published" as const,
        caption: "Mock LinkedIn publish",
        image_url: null,
        linkedin_post_id: "dev-linkedin-publication_new",
        linkedin_post_url: "https://linkedin.com/company/orion-media",
        failure_reason: null,
        attempts: 1,
        created_at: new Date().toISOString(),
        published_at: new Date().toISOString(),
      },
      201,
    ),
  ),
  http.post(`${base}/publishing/linkedin/content`, () =>
    ok({
      id: "publication_content",
      account_id: "tenant_orion",
      content_id: "content_1",
      scheduled_post_id: null,
      connection_id: "linkedin_orion",
      status: "published" as const,
      caption: "Mock approved content publish",
      image_url: null,
      linkedin_post_id: "dev-linkedin-publication_content",
      linkedin_post_url: "https://linkedin.com/company/orion-media",
      failure_reason: null,
      attempts: 1,
      created_at: new Date().toISOString(),
      published_at: new Date().toISOString(),
    }),
  ),
  http.post(`${base}/publishing/linkedin/refresh-tokens`, () => ok({ refreshed: 1 })),
  http.get(`${base}/scraper/jobs`, () =>
    ok({ view: productViews.scraper, items: scraperJobs.map(toRawScraperJob) }),
  ),
  http.post(`${base}/scraper/jobs`, async ({ request }) => {
    const body = (await request.json()) as {
      job_type: "url" | "serp" | "research";
      target: string;
      name: string;
      max_pages?: number;
      recurring?: boolean;
      interval_hours?: number | null;
    };
    const now = new Date().toISOString();
    const isResearch = body.job_type === "research";
    const sourceCount = isResearch ? (body.max_pages && body.max_pages > 1 ? body.max_pages : 4) : 1;
    return ok(
      toRawScraperJob({
        id: `scrape_${crypto.randomUUID()}`,
        accountId: "tenant_orion",
        createdBy: "user_owner",
        jobType: body.job_type,
        target: body.target,
        name: body.name,
        maxPages: sourceCount,
        status: "completed",
        recurring: body.recurring ?? false,
        intervalHours: body.interval_hours ?? null,
        nextRunAt: body.recurring ? new Date(Date.now() + (body.interval_hours ?? 24) * 3_600_000).toISOString() : null,
        lastRunAt: now,
        pagesProcessed: sourceCount,
        answer: isResearch
          ? `# ${body.target}\n\nGathered from ${sourceCount} source(s):\n\n## Example source\n\nSource: <https://example.com>\n\nMock research answer for "${body.target}" (mock API mode — no real scraping performed).`
          : null,
        failureReason: null,
        attempts: 1,
        createdAt: now,
        updatedAt: now,
      }),
      201,
    );
  }),
  http.get(`${base}/scraper/jobs/:jobId`, ({ params }) => {
    const job = scraperJobs.find((item) => item.id === params.jobId) ?? scraperJobs[0];
    return ok(toRawScraperJob(job));
  }),
  http.post(`${base}/scraper/jobs/:jobId/cancel`, ({ params }) => {
    const job = scraperJobs.find((item) => item.id === params.jobId) ?? scraperJobs[0];
    return ok(toRawScraperJob({ ...job, status: "cancelled", updatedAt: new Date().toISOString() }));
  }),
  http.get(`${base}/scraper/jobs/:jobId/documents`, ({ params }) =>
    ok(
      scrapedDocuments
        .filter((document) => document.jobId === params.jobId)
        .map((document) => ({
          id: document.id,
          job_id: document.jobId,
          account_id: document.accountId,
          job_type: document.jobType,
          source: document.source,
          title: document.title,
          text: document.text,
          data: document.data,
          fetched_at: document.fetchedAt,
        })),
    ),
  ),
  http.get(`${base}/notifications`, () =>
    ok({
      view: productViews.notifications,
      items: [
        {
          id: "notif_1",
          accountId: "tenant_orion",
          title: "LinkedIn post published",
          detail: "Product intelligence launch went live",
          category: "Publishing",
          status: "Unread",
          createdAt: new Date(Date.now() - 5 * 60_000).toISOString(),
        },
        {
          id: "notif_2",
          accountId: "tenant_orion",
          title: "Low credit balance",
          detail: "Your balance dropped below the low-balance threshold",
          category: "Credits",
          status: "Unread",
          createdAt: new Date(Date.now() - 3 * 3_600_000).toISOString(),
        },
        {
          id: "notif_3",
          accountId: "tenant_orion",
          title: "New team member",
          detail: "Nina Patel joined the workspace as Member",
          category: "Account",
          status: "Read",
          createdAt: new Date(Date.now() - 26 * 3_600_000).toISOString(),
        },
      ],
    }),
  ),
  http.get(`${base}/admin/overview`, () =>
    ok({ view: productViews.admin, health: serviceHealth, audit: [], flags: [] }),
  ),
  http.get(`${base}/admin/sessions`, () =>
    ok([
      {
        jti: "mock-jti-1",
        user_id: "user_owner",
        account_id: "tenant_orion",
        account_role: "Owner",
        platform_role: null,
      },
    ]),
  ),
  http.delete(`${base}/admin/sessions/:jti`, () => ok(undefined, 204)),
  http.get(`${base}/admin/accounts/:accountId/summary`, ({ params }) =>
    ok({
      account_id: params.accountId,
      plan_tier: "pro",
      seat_count: 5,
      member_count: 3,
      credit_balance: 12000,
      usage_tokens: 45000,
      usage_quota_tokens: 1_000_000,
    }),
  ),
  http.get(`${base}/admin/audit`, () => ok([])),
];
