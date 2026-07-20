export type RecurrenceFrequency = "daily" | "weekly" | "monthly" | "custom";
export interface Schedule {
  id: string;
  accountId: string;
  title: string;
  status: "Scheduled" | "Recurring" | "Paused" | "Failed";
  publishAt: string;
  timezone: string;
  recurrence?: { frequency: RecurrenceFrequency; rule?: string; nextRunAt: string };
}
export interface CreateScheduleRequest {
  title: string;
  frequency: RecurrenceFrequency;
  timezone: string;
  startAt: string;
}
