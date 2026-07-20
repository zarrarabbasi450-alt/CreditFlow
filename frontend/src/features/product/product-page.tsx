"use client";
import { motion } from "framer-motion";
import { ArrowUpRight, CheckCircle2, Clock, MoreHorizontal, Plus, Sparkles } from "lucide-react";
import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { RecurringScheduleForm } from "@/features/scheduler/recurring-form";
import { LinkedInImageForm } from "@/features/publishing/linkedin-image-form";
import { streamGeneration } from "@/lib/api/content";
import { useToast } from "@/components/toast";
import { useProductView } from "@/hooks/useProductView";
import { TeamManagement } from "@/features/team/team-management";
import { BillingManagement } from "@/features/billing/billing-management";
import { CreditsManagement } from "@/features/credits/credits-management";
import type { ActivityRow } from "@/types";
function SectionTabs({ section }: { section: string }) {
  const tabs: Record<string, string[]> = {
    billing: ["Overview", "Subscription", "Invoices", "Payment methods"],
    credits: ["Overview", "Ledger", "Marketplace"],
    scheduler: ["Calendar", "Recurring"],
    publishing: ["Overview", "LinkedIn", "LinkedIn image", "History"],
    settings: ["Account", "Sessions", "API keys"],
    team: ["Members", "Invitations"],
    admin: ["Overview", "Accounts", "Users", "Health", "Audit", "Failed jobs", "Feature flags"],
  };
  return tabs[section] ? (
    <div className="tabs">
      {tabs[section].map((tab) => (
        <a
          key={tab}
          href={
            tab === "Overview" || tab === "Calendar"
              ? `/${section}`
              : `/${section}/${tab.toLowerCase().replaceAll(" ", "-")}`
          }
        >
          {tab}
        </a>
      ))}
    </div>
  ) : null;
}
export function ProductPage({ section, subsection }: { section: string; subsection?: string }) {
  const { data: base, isLoading, error } = useProductView(section);
  const { notify } = useToast();
  const [prompt, setPrompt] = useState("");
  const [output, setOutput] = useState("");
  const [generating, setGenerating] = useState(false);
  const special =
    subsection === "recurring"
      ? "recurring"
      : subsection === "linkedin-image"
        ? "image"
        : section === "ai-studio"
          ? "ai"
          : null;
  async function generate() {
    if (!prompt.trim()) return;
    setGenerating(true);
    setOutput("");
    for await (const chunk of streamGeneration(prompt))
      if (chunk.type === "token") setOutput((value) => value + chunk.value);
    setGenerating(false);
  }
  if (isLoading || !base)
    return (
      <div className="loading-screen">
        <Sparkles className="animate-pulse" />
        {error ? "Unable to load this workspace." : "Loading workspace…"}
      </div>
    );
  const runPrimaryAction = () => {
    if (section === "team") {
      document.getElementById("team-invite-email")?.focus();
      return;
    }
    notify(`${base.action} action opened`);
  };
  const title = subsection
    ? subsection.replaceAll("-", " ").replace(/\b\w/g, (character) => character.toUpperCase())
    : base.title;
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <SectionTabs section={section} />
      <div className="page-heading">
        <div>
          <span>{base.eyebrow}</span>
          <h1>{title}</h1>
          <p>{base.description}</p>
        </div>
        {section !== "settings" && section !== "billing" && (
          <button className="primary-button" onClick={runPrimaryAction}>
            <Plus />
            {base.action}
          </button>
        )}
      </div>
      {base.metrics && (
        <div className="metric-grid">
          {base.metrics.map((metric) => (
            <article key={metric.label}>
              <div>
                <span>{metric.label}</span>
                <ArrowUpRight />
              </div>
              <strong>{metric.value}</strong>
              <small>{metric.change}</small>
            </article>
          ))}
        </div>
      )}
      {special === "recurring" && (
        <Panel title="Create a recurring schedule">
          <RecurringScheduleForm />
        </Panel>
      )}
      {special === "image" && (
        <Panel title="Publish an image post">
          <LinkedInImageForm />
        </Panel>
      )}
      {special === "ai" && (
        <div className="studio-grid">
          <Panel title="Generation brief">
            <div className="generator">
              <label htmlFor="prompt">What would you like to create?</label>
              <textarea
                id="prompt"
                rows={9}
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="A LinkedIn post announcing our new analytics workspace…"
              />
              <label htmlFor="model">Model</label>
              <select id="model">
                <option>Claude 3.7 Sonnet</option>
                <option>GPT-4.1</option>
                <option>Gemini 2.5 Pro</option>
              </select>
              <button className="primary-button" disabled={generating} onClick={generate}>
                <Sparkles />
                {generating ? "Generating…" : "Generate content"}
              </button>
            </div>
          </Panel>
          <Panel title="Streaming output">
            <div className="output">
              {output ||
                "Your generated content will appear here token by token. Usage and credit cost are recorded with every run."}
            </div>
          </Panel>
        </div>
      )}
      {section === "team" && (
        <Panel title="Members">
          <TeamManagement />
        </Panel>
      )}
      {section === "billing" && (
        <Panel title="Subscription & invoices">
          <BillingManagement />
        </Panel>
      )}
      {section === "credits" && (
        <Panel title="Balance, ledger & marketplace">
          <CreditsManagement />
        </Panel>
      )}
      {!special &&
        section !== "dashboard" &&
        section !== "usage" &&
        section !== "team" &&
        section !== "billing" &&
        section !== "credits" && (
          <Panel title={section === "admin" ? "Service health" : "Recent activity"}>
            <DataRows rows={base.rows ?? []} />
          </Panel>
        )}
      {(section === "dashboard" || section === "usage") && (
        <div className="dashboard-grid">
          <Panel title={section === "usage" ? "Daily token volume" : "Content momentum"}>
            <div className="chart">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={base.chart ?? []}>
                  <defs>
                    <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#7c5cff" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#7c5cff" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="day" />
                  <YAxis hide />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey={section === "usage" ? "tokens" : "posts"}
                    stroke="#7c5cff"
                    strokeWidth={3}
                    fill="url(#fill)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <Panel title="Recent activity">
            <DataRows rows={base.rows ?? []} />
          </Panel>
        </div>
      )}
    </motion.div>
  );
}
function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <h2>{title}</h2>
        <button aria-label="More options">
          <MoreHorizontal />
        </button>
      </div>
      {children}
    </section>
  );
}
function DataRows({ rows }: { rows: ActivityRow[] }) {
  return (
    <div className="data-rows">
      {rows.map((row, index) => (
        <div key={row.title + index}>
          <span className="row-icon">{row.status.includes("Scheduled") ? <Clock /> : <CheckCircle2 />}</span>
          <div>
            <strong>{row.title}</strong>
            <small>{row.detail}</small>
          </div>
          <em>{row.status || row.amount}</em>
        </div>
      ))}
    </div>
  );
}
