import { request } from "./client";
import type {
  CreateScheduleRequest,
  ProductView,
  Schedule,
  SchedulerCalendar,
  SchedulerSummary,
  UpdateScheduleRequest,
} from "@/types";

interface RawSchedule {
  id: string;
  account_id: string;
  content_id: string;
  title: string;
  status: Schedule["status"];
  publish_at: string;
  publish_at_local: string;
  timezone: string;
  fired_at?: string | null;
  cancelled_at?: string | null;
  created_at: string;
  updated_at: string;
}

interface RawCalendar {
  items: RawSchedule[];
  timezone: string;
  range_start: string;
  range_end: string;
}

interface RawSummary {
  scheduled_count: number;
  due_count: number;
  next_publish_at?: string | null;
}

const schedulerView: ProductView = {
  title: "Publishing schedule",
  eyebrow: "Calendar",
  description: "Attach approved content to future publish times and let Scheduler hand it to publishing when due.",
  action: "Schedule content",
};

const toSchedule = (value: RawSchedule): Schedule => ({
  id: value.id,
  accountId: value.account_id,
  contentId: value.content_id,
  title: value.title,
  status: value.status,
  publishAt: value.publish_at,
  publishAtLocal: value.publish_at_local,
  timezone: value.timezone,
  firedAt: value.fired_at ?? null,
  cancelledAt: value.cancelled_at ?? null,
  createdAt: value.created_at,
  updatedAt: value.updated_at,
});

const toPayload = (data: CreateScheduleRequest | UpdateScheduleRequest) => ({
  ...(data && "contentId" in data ? { content_id: data.contentId } : {}),
  ...(data && "title" in data ? { title: data.title } : {}),
  publish_at: data.publishAt,
  timezone: data.timezone,
});

export const getSchedules = async (params?: { start?: string; end?: string; timezone?: string }) => {
  const response = await request<RawCalendar>({
    url: "/scheduler",
    method: "GET",
    params: { start: params?.start, end: params?.end, timezone: params?.timezone },
  });
  return {
    view: schedulerView,
    items: response.items.map(toSchedule),
    timezone: response.timezone,
    rangeStart: response.range_start,
    rangeEnd: response.range_end,
  } satisfies SchedulerCalendar;
};

export const createSchedule = (data: CreateScheduleRequest) =>
  request<RawSchedule>({ url: "/scheduler", method: "POST", data: toPayload(data) }).then(toSchedule);

export const updateSchedule = (scheduleId: string, data: UpdateScheduleRequest) =>
  request<RawSchedule>({ url: `/scheduler/${scheduleId}`, method: "PATCH", data: toPayload(data) }).then(toSchedule);

export const cancelSchedule = (scheduleId: string) =>
  request<RawSchedule>({ url: `/scheduler/${scheduleId}`, method: "DELETE" }).then(toSchedule);

export const getSchedulerSummary = () =>
  request<RawSummary>({ url: "/scheduler/summary", method: "GET" }).then(
    (value): SchedulerSummary => ({
      scheduledCount: value.scheduled_count,
      dueCount: value.due_count,
      nextPublishAt: value.next_publish_at ?? null,
    }),
  );
