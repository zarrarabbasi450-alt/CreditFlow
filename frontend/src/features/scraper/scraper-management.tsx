"use client";

import { ArrowLeft, Clock, Loader2, RotateCcw, Search, Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";
import { useToast } from "@/components/toast";
import { useScraper, useScraperJobStatus, useScraperMutations } from "@/hooks/useScraper";
import { setScraperPromptSeed } from "@/lib/scraper-handoff";
import type { ScraperJob } from "@/types";

const URL_PATTERN = /^https?:\/\/\S+$/i;

function statusLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function buildName(input: string) {
  const trimmed = input.trim();
  return trimmed.length <= 60 ? trimmed : `${trimmed.slice(0, 57)}...`;
}

export function ScraperManagement() {
  const { notify } = useToast();
  const scraper = useScraper();
  const mutations = useScraperMutations();
  const [query, setQuery] = useState("");
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [showRepeatOptions, setShowRepeatOptions] = useState(false);
  const [repeat, setRepeat] = useState(false);
  const [intervalHours, setIntervalHours] = useState(24);

  const jobs = scraper.data?.items ?? [];
  const active = useScraperJobStatus(activeJobId);
  const activeIsPending = active.data && !["completed", "failed", "cancelled"].includes(active.data.status);
  const busy = mutations.create.isPending || Boolean(activeIsPending);

  async function search() {
    const trimmed = query.trim();
    if (!trimmed) {
      notify("Type a question or paste a URL to search.");
      return;
    }
    const isUrl = URL_PATTERN.test(trimmed);
    try {
      const job = await mutations.create.mutateAsync({
        jobType: isUrl ? "url" : "research",
        target: trimmed,
        name: buildName(trimmed),
        recurring: repeat,
        intervalHours: repeat ? intervalHours : null,
      });
      setActiveJobId(job.id);
      setQuery("");
      setRepeat(false);
      setShowRepeatOptions(false);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Unable to run that search");
    }
  }

  if (scraper.isLoading) return <p className="scheduler-note">Loading scraper...</p>;
  if (scraper.error) return <p className="scheduler-note error">Unable to load the scraper service.</p>;

  return (
    <div className="scraper-management">
      <div className="scraper-search-bar">
        <Search className="scraper-search-icon" />
        <input
          id="scraper-job-name"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void search();
          }}
          placeholder="Ask a research question or paste a URL to analyze"
        />
        <button className="primary-button" type="button" disabled={busy} onClick={() => void search()}>
          {busy ? <Loader2 className="animate-spin" /> : <Sparkles />}
          {busy ? "Working..." : "Search"}
        </button>
      </div>

      <div className="scraper-repeat-row">
        {!showRepeatOptions ? (
          <button type="button" className="scraper-repeat-toggle" onClick={() => setShowRepeatOptions(true)}>
            <RotateCcw />
            Repeat this search automatically
          </button>
        ) : (
          <label className="toggle-row">
            <input
              type="checkbox"
              checked={repeat}
              onChange={(event) => setRepeat(event.target.checked)}
            />
            Repeat every
            <input
              type="number"
              min={1}
              max={168}
              value={intervalHours}
              disabled={!repeat}
              onChange={(event) => setIntervalHours(Number(event.target.value) || 24)}
              className="scraper-interval-input"
            />
            hours
          </label>
        )}
      </div>

      {activeJobId && active.data && (
        <div className="scraper-answer">
          <button
            type="button"
            className="scraper-answer-close"
            onClick={() => setActiveJobId(null)}
          >
            <ArrowLeft />
            Back to search
          </button>
          {activeIsPending && (
            <p className="scraper-note">
              <Loader2 className="animate-spin" /> Gathering sources for &ldquo;{active.data.target}&rdquo;...
            </p>
          )}
          {active.data.status === "failed" && (
            <p className="scraper-warning">{active.data.failureReason ?? "That search failed."}</p>
          )}
          {active.data.status === "completed" && active.data.answerHtml && (
            <>
              <div dangerouslySetInnerHTML={{ __html: active.data.answerHtml }} />
              {active.data.answer && (
                <button
                  type="button"
                  className="primary-button scraper-use-in-studio"
                  onClick={() => {
                    setScraperPromptSeed(
                      `Using this research on "${active.data!.target}":\n\n${active.data!.answer}\n\n---\nWrite a post that shares the key insight from this research.`,
                    );
                    window.location.assign("/ai-studio");
                  }}
                >
                  <Wand2 />
                  Use in AI Studio
                </button>
              )}
            </>
          )}
        </div>
      )}

      {jobs.length > 0 && (
        <div className="data-rows scraper-rows">
          {jobs.map((job) => (
            <button
              key={job.id}
              type="button"
              className="scraper-history-row"
              onClick={() => setActiveJobId(job.id)}
            >
              <span className="row-icon">
                <Clock />
              </span>
              <div>
                <strong>{job.name}</strong>
                <small>
                  {new Date(job.createdAt).toLocaleString()}
                  {job.recurring
                    ? ` · repeats every ${job.intervalHours}h${
                        job.nextRunAt ? ` · next ${new Date(job.nextRunAt).toLocaleString()}` : ""
                      }`
                    : ""}
                </small>
              </div>
              <em className={jobTone(job)}>{statusLabel(job.status)}</em>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function jobTone(job: ScraperJob) {
  if (job.status === "completed") return "success";
  if (job.status === "failed" || job.status === "cancelled") return "danger";
  return "muted";
}
