import { describe, expect, it } from "vitest";
import { loginSchema, recurringScheduleSchema } from "@/lib/schemas";
describe("shared validation", () => {
  it("accepts the documented demo credentials", () => {
    expect(loginSchema.safeParse({ email: "owner@orionmedia.com", password: "Password123!" }).success).toBe(
      true,
    );
  });
  it("requires timezone and start time for recurrence", () => {
    expect(
      recurringScheduleSchema.safeParse({
        title: "Weekly post",
        frequency: "weekly",
        timezone: "",
        startAt: "",
      }).success,
    ).toBe(false);
  });
});
