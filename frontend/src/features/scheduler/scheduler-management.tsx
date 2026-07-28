"use client";

import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin, { type DateClickArg } from "@fullcalendar/interaction";
import FullCalendar from "@fullcalendar/react";
import type { DatesSetArg, EventClickArg, EventInput } from "@fullcalendar/core";
import { CalendarClock, RotateCcw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useToast } from "@/components/toast";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { useContent } from "@/hooks/useContent";
import { useScheduler, useSchedulerMutations, useSchedulerSummary } from "@/hooks/useScheduler";
import type { ContentItem, Schedule } from "@/types";

const statusColors: Record<string, string> = {
  scheduled: "#7c5cff",
  fired: "#1fae6d",
  cancelled: "#9298a8",
  failed: "#dc2946",
};

const browserTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

function toDatetimeLocal(value: Date) {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function fromDatetimeLocal(value: string) {
  return new Date(value).toISOString();
}

function scheduleLabel(item: Schedule) {
  return new Date(item.publishAtLocal || item.publishAt).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatIso(value: string) {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function eligibleContent(items: ContentItem[]) {
  return items.filter((item) => item.contentType === "post" && item.status !== "published");
}

export function SchedulerManagement({ subsection }: { subsection?: string }) {
  const { notify } = useToast();
  const timezone = browserTimezone();
  const defaultRange = useMemo(() => {
    const now = new Date();
    const start = new Date(now);
    start.setDate(1);
    start.setHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setDate(end.getDate() + 45);
    return { start: start.toISOString(), end: end.toISOString() };
  }, []);
  // Calendar's own visible range — FullCalendar's `datesSet` callback keeps this
  // in sync as the user navigates months, so the underlying query (and thus
  // which events are fetched) tracks whatever is actually on screen.
  const [visibleRange, setVisibleRange] = useState(defaultRange);

  const scheduler = useScheduler({ ...visibleRange, timezone });
  const summary = useSchedulerSummary();
  const content = useContent();
  const mutations = useSchedulerMutations();
  const [contentId, setContentId] = useState("");
  // Date comes only from clicking a day on the calendar below — the calendar
  // is the date picker now, this is just the hour/minute for that day.
  const [publishDate, setPublishDate] = useState<string | null>(null);
  const [publishTime, setPublishTime] = useState("09:00");
  const [rescheduleValues, setRescheduleValues] = useState<Record<string, string>>({});
  const [pendingCancel, setPendingCancel] = useState<Schedule | null>(null);

  const items = useMemo(() => scheduler.data?.items ?? [], [scheduler.data?.items]);
  const activeItems = items.filter((item) => item.status === "scheduled");
  const historicalItems = items.filter((item) => item.status !== "scheduled");
  const activeScheduleByContentId = useMemo(
    () => new Map(activeItems.map((item) => [item.contentId, item])),
    [activeItems],
  );
  const posts = useMemo(() => eligibleContent(content.data?.items ?? []), [content.data?.items]);
  const selected = posts.find((item) => item.id === contentId) ?? null;
  const selectedActiveSchedule = selected ? activeScheduleByContentId.get(selected.id) : undefined;
  const busy = mutations.create.isPending || mutations.update.isPending || mutations.cancel.isPending;
  const calendarEvents: EventInput[] = useMemo(
    () =>
      items.map((item) => ({
        id: item.id,
        title: item.title,
        start: item.publishAtLocal || item.publishAt,
        backgroundColor: statusColors[item.status],
        borderColor: statusColors[item.status],
      })),
    [items],
  );

  function onEventClick(info: EventClickArg) {
    const item = items.find((value) => value.id === info.event.id);
    if (!item) return;
    notify(`${item.title} — ${scheduleLabel(item)} · ${item.status}`);
  }

  function onDatesSet(info: DatesSetArg) {
    setVisibleRange((current) => {
      const nextStart = info.start.toISOString();
      const nextEnd = info.end.toISOString();
      return current.start === nextStart && current.end === nextEnd
        ? current
        : { start: nextStart, end: nextEnd };
    });
  }

  function onDateClick(info: DateClickArg) {
    setPublishDate(info.dateStr);
    document.getElementById("scheduler-content")?.focus();
  }

  function combinedPublishAt(): string | null {
    if (!publishDate) return null;
    const [hours, minutes] = publishTime.split(":").map(Number);
    const combined = new Date(`${publishDate}T00:00:00`);
    combined.setHours(hours || 0, minutes || 0, 0, 0);
    return combined.toISOString();
  }

  async function createSchedule() {
    const target = selected;
    if (!target) {
      notify("Select a draft before scheduling.");
      return;
    }
    const publishAt = combinedPublishAt();
    if (!publishAt) {
      notify("Click a date on the calendar below to choose when to publish.");
      return;
    }
    if (selectedActiveSchedule) {
      notify("This draft is already scheduled. Cancel or reschedule its current schedule first.");
      return;
    }
    try {
      await mutations.create.mutateAsync({
        contentId: target.id,
        title: target.title,
        publishAt,
        timezone,
      });
      notify("Content scheduled");
      setContentId("");
      setPublishDate(null);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Unable to schedule content");
    }
  }

  async function reschedule(item: Schedule) {
    const value = rescheduleValues[item.id];
    if (!value) return;
    try {
      await mutations.update.mutateAsync({
        id: item.id,
        payload: { publishAt: fromDatetimeLocal(value), timezone },
      });
      notify("Schedule updated");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Unable to reschedule content");
    }
  }

  async function cancel(item: Schedule) {
    try {
      await mutations.cancel.mutateAsync(item.id);
      notify("Schedule cancelled");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Unable to cancel schedule");
    } finally {
      setPendingCancel(null);
    }
  }

  if (subsection === "recurring") {
    return (
      <div className="scheduler-management">
        <div className="scheduler-summary-grid">
          <article>
            <span>Celery Beat</span>
            <strong>Every 60 seconds</strong>
            <small>Scans due scheduled_posts and publishes content.scheduled</small>
          </article>
          <article>
            <span>Due now</span>
            <strong>{summary.data?.dueCount ?? 0}</strong>
            <small>Protected by Redis idempotency locks</small>
          </article>
        </div>
        <button
          className="secondary-button scheduler-refresh"
          type="button"
          onClick={() =>
            void Promise.all([scheduler.refetch(), summary.refetch()]).then(() => notify("Scheduler refreshed"))
          }
        >
          <RotateCcw />
          Refresh scheduler status
        </button>
        <p className="scheduler-note">
          This service owns one-time scheduling. Recurring campaign rules will belong to a later workflow layer; the
          current periodic engine is Celery Beat firing due posts safely.
        </p>
      </div>
    );
  }

  return (
    <div className="scheduler-management">
      <div className="scheduler-summary-grid">
        <article>
          <span>Scheduled posts</span>
          <strong>{summary.data?.scheduledCount ?? activeItems.length}</strong>
          <small>Active in this workspace</small>
        </article>
        <article>
          <span>Next publish</span>
          <strong>{summary.data?.nextPublishAt ? formatIso(summary.data.nextPublishAt) : "None"}</strong>
          <small>Stored in UTC, shown in {timezone}</small>
        </article>
      </div>

      <div className="scheduler-create-grid">
        <label>
          Content item
          <select id="scheduler-content" value={contentId} onChange={(event) => setContentId(event.target.value)}>
            <option value="">Select a draft</option>
            {posts.length === 0 && <option value="">No drafts available</option>}
            {posts.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title} · {item.status}
                {activeScheduleByContentId.has(item.id) ? " · already scheduled" : ""}
              </option>
            ))}
          </select>
          {selectedActiveSchedule && (
            <small className="scheduler-warning">
              Already scheduled for {scheduleLabel(selectedActiveSchedule)}. Cancel or reschedule it below first.
            </small>
          )}
        </label>
        <label>
          Publish date
          <div className="scheduler-date-picked">
            {publishDate
              ? new Date(`${publishDate}T00:00:00`).toLocaleDateString(undefined, {
                  weekday: "short",
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })
              : "Click a date on the calendar below"}
          </div>
        </label>
        <label>
          Publish time
          <input
            id="scheduler-publish-time"
            type="time"
            value={publishTime}
            onChange={(event) => setPublishTime(event.target.value)}
          />
        </label>
        <button
          className="primary-button"
          type="button"
          disabled={busy || !selected || !publishDate || Boolean(selectedActiveSchedule)}
          onClick={createSchedule}
        >
          <CalendarClock />
          Schedule content
        </button>
      </div>

      {scheduler.isLoading && <p className="scheduler-note">Loading calendar…</p>}
      {scheduler.error && <p className="scheduler-note error">Unable to load the publishing calendar.</p>}

      <div className="scheduler-calendar">
        <FullCalendar
          plugins={[dayGridPlugin, interactionPlugin]}
          initialView="dayGridMonth"
          height="auto"
          headerToolbar={{ left: "prev,next today", center: "title", right: "" }}
          events={calendarEvents}
          eventClick={onEventClick}
          dateClick={onDateClick}
          datesSet={onDatesSet}
        />
      </div>

      <div className="data-rows scheduler-rows">
        {activeItems.length === 0 && <p>No scheduled posts yet.</p>}
        {activeItems.map((item) => (
          <div key={item.id}>
            <span className="row-icon">
              <CalendarClock />
            </span>
            <div>
              <strong>{item.title}</strong>
              <small>
                {scheduleLabel(item)} · {item.timezone} · {item.status}
              </small>
              <input
                type="datetime-local"
                value={rescheduleValues[item.id] ?? toDatetimeLocal(new Date(item.publishAtLocal || item.publishAt))}
                onChange={(event) =>
                  setRescheduleValues((values) => ({ ...values, [item.id]: event.target.value }))
                }
              />
            </div>
            <div className="scheduler-row-actions">
              <button className="secondary-button" type="button" disabled={busy} onClick={() => void reschedule(item)}>
                <RotateCcw />
                Reschedule
              </button>
              <button
                className="secondary-button danger"
                type="button"
                disabled={busy}
                onClick={() => setPendingCancel(item)}
              >
                <Trash2 />
                Cancel
              </button>
            </div>
          </div>
        ))}
      </div>

      {historicalItems.length > 0 && (
        <div className="data-rows scheduler-rows">
          {historicalItems.map((item) => (
            <div key={item.id}>
              <span className="row-icon">
                <CalendarClock />
              </span>
              <div>
                <strong>{item.title}</strong>
                <small>
                  {scheduleLabel(item)} · {item.status}
                </small>
              </div>
              <em>{item.status}</em>
            </div>
          ))}
        </div>
      )}
      <ConfirmDialog
        open={pendingCancel !== null}
        title="Cancel this schedule?"
        description={
          pendingCancel
            ? `"${pendingCancel.title}" will no longer publish at ${scheduleLabel(pendingCancel)}.`
            : ""
        }
        confirmLabel="Cancel schedule"
        cancelLabel="Keep it"
        busy={mutations.cancel.isPending}
        onCancel={() => setPendingCancel(null)}
        onConfirm={() => {
          if (pendingCancel) void cancel(pendingCancel);
        }}
      />
    </div>
  );
}
