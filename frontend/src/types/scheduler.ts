import type { ProductView } from "./api";

export type ScheduleStatus = "scheduled" | "cancelled" | "fired" | "failed";

export interface Schedule {
  id: string;
  accountId: string;
  contentId: string;
  title: string;
  status: ScheduleStatus;
  publishAt: string;
  publishAtLocal: string;
  timezone: string;
  firedAt?: string | null;
  cancelledAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface CreateScheduleRequest {
  contentId: string;
  title: string;
  publishAt: string;
  timezone: string;
}

export interface UpdateScheduleRequest {
  publishAt: string;
  timezone: string;
}

export interface SchedulerCalendar {
  view: ProductView;
  items: Schedule[];
  timezone: string;
  rangeStart: string;
  rangeEnd: string;
}

export interface SchedulerSummary {
  scheduledCount: number;
  dueCount: number;
  nextPublishAt?: string | null;
}
