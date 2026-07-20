import { http, HttpResponse } from "msw";
import {
  billing,
  contentItems,
  credentials,
  credits,
  productViews,
  schedules,
  scraperJobs,
  serviceHealth,
  sessionFor,
  usage,
  users,
} from "./data";
import type { ApiResponse, Role } from "@/types";
const base = "*/api/v1";
const meta = () => ({
  requestId: `req_${crypto.randomUUID()}`,
  correlationId: `corr_${crypto.randomUUID()}`,
});
const ok = <T>(data: T, status = 200) =>
  HttpResponse.json<ApiResponse<T>>({ success: true, data, meta: meta() }, { status });
export const handlers = [
  http.get(`${base}/auth/me`, () => ok(sessionFor("Owner", "Avery Moore", "owner@orionmedia.com").user)),
  http.post(`${base}/auth/development-role`, async ({ request }) => {
    const { role } = (await request.json()) as { role: Role };
    const profile = credentials.find((item) => item.role === role) ?? credentials[0];
    return ok(sessionFor(profile.role, profile.name, profile.email));
  }),
  http.get(`${base}/dashboard`, () => ok(productViews.dashboard)),
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
  http.get(`${base}/usage/summary`, () => ok(usage)),
  http.get(`${base}/content`, () => ok({ view: productViews.content, items: contentItems })),
  http.get(`${base}/ai/overview`, () => ok(productViews["ai-studio"])),
  http.post(`${base}/ai/generations`, async ({ request }) => {
    const body = (await request.json()) as { prompt: string };
    return ok(
      {
        generationId: "generation_mock",
        tokens:
          `Turn ${body.prompt} into a crisp, credible narrative: lead with the customer tension, show the practical shift, support it with evidence, and close with one clear action.`.split(
            " ",
          ),
      },
      201,
    );
  }),
  http.get(`${base}/scheduler`, () => ok({ view: productViews.scheduler, items: schedules })),
  http.post(`${base}/scheduler`, async ({ request }) =>
    ok(
      {
        ...((await request.json()) as object),
        id: "schedule_new",
        accountId: "tenant_orion",
        status: "Recurring",
        publishAt: "2026-07-22T09:30:00+05:00",
      },
      201,
    ),
  ),
  http.get(`${base}/publishing`, () =>
    ok({
      view: productViews.publishing,
      connections: [
        {
          id: "linkedin_orion",
          accountId: "tenant_orion",
          provider: "linkedin" as const,
          profileName: "Orion Media Group",
          status: "Connected" as const,
          connectedAt: "2026-01-12T00:00:00Z",
        },
      ],
    }),
  ),
  http.post(`${base}/publishing/linkedin`, () =>
    ok(
      {
        id: "publication_new",
        provider: "linkedin" as const,
        status: "Queued" as const,
        createdAt: new Date().toISOString(),
      },
      201,
    ),
  ),
  http.get(`${base}/scraper/jobs`, () => ok({ view: productViews.scraper, items: scraperJobs })),
  http.get(`${base}/notifications`, () => ok({ view: productViews.notifications, items: [] })),
  http.get(`${base}/admin/overview`, () =>
    ok({ view: productViews.admin, health: serviceHealth, audit: [], flags: [] }),
  ),
];
