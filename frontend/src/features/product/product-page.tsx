"use client";
import { motion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, CheckCircle2, Clock, Image as ImageIcon, Plus, Sparkles, Square } from "lucide-react";
import Image from "next/image";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { RecurringScheduleForm } from "@/features/scheduler/recurring-form";
import { LinkedInImageForm } from "@/features/publishing/linkedin-image-form";
import { cancelGeneration, generateImage, streamGeneration } from "@/lib/api/content";
import { useToast } from "@/components/toast";
import { useProductView } from "@/hooks/useProductView";
import { usePromptHistory } from "@/hooks/useAI";
import { TeamManagement } from "@/features/team/team-management";
import { BillingManagement } from "@/features/billing/billing-management";
import { CreditsManagement } from "@/features/credits/credits-management";
import { AdminOperations } from "@/features/admin/operations";
import { AccountSettings } from "@/features/settings/account-settings";
import { UsageManagement } from "@/features/usage/usage-management";
import { ContentManagement } from "@/features/content/content-management";
import type { ActivityRow } from "@/types";
function SectionTabs({ section, subsection }: { section: string; subsection?: string }) {
  const tabs: Record<string, string[]> = {
    billing: ["Overview", "Subscription", "Invoices", "Payment methods"],
    credits: ["Overview", "Ledger", "Marketplace"],
    scheduler: ["Calendar", "Recurring"],
    publishing: ["Overview", "LinkedIn", "LinkedIn image", "History"],
    "ai-studio": ["Composer", "Chat history", "Images"],
    content: ["Overview", "Drafts", "Approved", "Published"],
    settings: ["Account", "Sessions", "API keys"],
    team: ["Members", "Invitations"],
    usage: ["Overview", "Ledger", "Models"],
    admin: ["Overview", "Accounts", "Users", "Health", "Audit", "Failed jobs", "Feature flags"],
  };
  return tabs[section] ? (
    <div className="tabs">
      {tabs[section].map((tab) => {
        const slug = tab.toLowerCase().replaceAll(" ", "-");
        const root = tab === "Overview" || tab === "Calendar" || tab === "Composer";
        return (
          <a
            key={tab}
            className={(root ? !subsection : subsection === slug) ? "active" : undefined}
            href={root ? `/${section}` : `/${section}/${slug}`}
          >
            {tab}
          </a>
        );
      })}
    </div>
  ) : null;
}
export function ProductPage({ section, subsection }: { section: string; subsection?: string }) {
  const { data: base, isLoading, error, refetch } = useProductView(section);
  const history = usePromptHistory(section === "ai-studio");
  const queryClient = useQueryClient();
  const { notify } = useToast();
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState<"fast" | "quality">("fast");
  const [includeImage, setIncludeImage] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
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
    setImageUrl(null);
    try {
      for await (const chunk of streamGeneration({ prompt, model, generateImage: includeImage })) {
        setCurrentJobId(chunk.generationId);
        if (chunk.type === "token") setOutput((value) => value + chunk.value);
        if (chunk.type === "complete" && chunk.imageUrl) setImageUrl(chunk.imageUrl);
        if (chunk.type === "failed") throw new Error(chunk.value);
        if (chunk.type === "cancelled") {
          setOutput((value) => value + `\n${chunk.value}`);
          notify("Generation cancelled");
          return;
        }
      }
      await Promise.all([
        history.refetch(),
        queryClient.invalidateQueries({ queryKey: ["usage"] }),
        queryClient.invalidateQueries({ queryKey: ["product-view", "usage"] }),
      ]);
      notify("Generation completed");
    } catch (generationError) {
      notify(generationError instanceof Error ? generationError.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }
  async function cancelCurrentGeneration() {
    if (!currentJobId) return;
    await cancelGeneration(currentJobId);
    setGenerating(false);
    notify("Generation cancellation requested");
  }
  async function createImage() {
    if (!prompt.trim()) return;
    const image = await generateImage(prompt);
    setImageUrl(image.imageUrl);
    notify("Image generated");
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
    if (section === "admin") {
      window.location.assign("/admin/users");
      return;
    }
    if (section === "credits") {
      document.getElementById("listing-credits")?.focus();
      return;
    }
    if (section === "usage") {
      void Promise.all([refetch(), queryClient.invalidateQueries({ queryKey: ["usage"] })]).then(() =>
        notify("Usage refreshed"),
      );
      return;
    }
    if (section === "content") {
      document.getElementById("content-title")?.focus();
      return;
    }
    notify(`${base.action} action opened`);
  };
  const title = subsection
    ? subsection.replaceAll("-", " ").replace(/\b\w/g, (character) => character.toUpperCase())
    : base.title;
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <SectionTabs section={section} subsection={subsection} />
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
      {base.metrics && !(section === "admin" && subsection) && (
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
      {special === "ai" && subsection === "chat-history" && (
        <Panel title="Chat history">
          <div className="data-rows history-rows">
            {history.isLoading && <p>Loading prompt history...</p>}
            {!history.isLoading && (history.data ?? []).length === 0 && <p>No prompt history yet.</p>}
            {(history.data ?? []).map((item) => (
              <div key={item.id}>
                <div>
                  <strong>{item.prompt}</strong>
                  <small>
                    {item.model} · {item.totalTokens.toLocaleString()} tokens · $
                    {(item.costMicrousd / 1_000_000).toFixed(4)}
                  </small>
                  <div className="history-response">
                    <ReactMarkdown>{item.response || "_No response stored for this generation._"}</ReactMarkdown>
                  </div>
                </div>
                <em>{new Date(item.createdAt).toLocaleString()}</em>
              </div>
            ))}
          </div>
        </Panel>
      )}
      {special === "ai" && subsection === "images" && (
        <Panel title="Generated images">
          <div className="empty-state">
            <ImageIcon />
            <p>Image history storage is prepared in the AI service. Generate an image from Composer first.</p>
          </div>
        </Panel>
      )}
      {special === "ai" && !subsection && (
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
              <select id="model" value={model} onChange={(event) => setModel(event.target.value as "fast" | "quality")}>
                <option value="fast">Fast draft</option>
                <option value="quality">Quality draft</option>
              </select>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={includeImage}
                  onChange={(event) => setIncludeImage(event.target.checked)}
                />
                Generate image for this post
              </label>
              <button className="secondary-button" disabled={!generating || !currentJobId} onClick={cancelCurrentGeneration}>
                <Square />
                Cancel generation
              </button>
              <button className="secondary-button" disabled={!prompt.trim()} onClick={createImage}>
                <ImageIcon />
                Generate image only
              </button>
              <button className="primary-button" disabled={generating} onClick={generate}>
                <Sparkles />
                {generating ? "Generating…" : "Generate content"}
              </button>
            </div>
          </Panel>
          <Panel title="Streaming output">
            <div className="output">
              {output ? (
                <ReactMarkdown>{output}</ReactMarkdown>
              ) : (
                "Your generated content will appear here token by token. Usage and credit cost are recorded with every run."
              )}
              {imageUrl && (
                <div className="generated-image-card">
                  <Image
                    src={imageUrl}
                    alt="Generated visual for this post"
                    width={900}
                    height={520}
                    unoptimized
                  />
                  <a className="image-link" href={imageUrl} target="_blank" rel="noreferrer">
                    Open full-size generated image
                  </a>
                </div>
              )}
            </div>
          </Panel>
          <Panel title="Prompt history">
            <div className="data-rows">
              {history.isLoading && <p>Loading prompt historyâ€¦</p>}
              {!history.isLoading && (history.data ?? []).length === 0 && <p>No prompt history yet.</p>}
              {(history.data ?? []).slice(0, 5).map((item) => (
                <div key={item.id}>
                  <div>
                    <strong>{item.prompt}</strong>
                    <small>
                      {item.model} Â· {item.totalTokens.toLocaleString()} tokens
                    </small>
                  </div>
                  <em>{new Date(item.createdAt).toLocaleDateString()}</em>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}
      {section === "team" && (
        <Panel title="Members">
          <TeamManagement subsection={subsection} />
        </Panel>
      )}
      {section === "billing" && (
        <Panel title="Subscription & invoices">
          <BillingManagement subsection={subsection} />
        </Panel>
      )}
      {section === "credits" && (
        <Panel title="Balance, ledger & marketplace">
          <CreditsManagement subsection={subsection} />
        </Panel>
      )}
      {section === "settings" && (
        <Panel title={subsection ? title : "Account settings"}>
          <AccountSettings subsection={subsection} />
        </Panel>
      )}
      {section === "admin" && (
        <Panel title={subsection ? title : "Platform operations"}>
          <AdminOperations subsection={subsection} />
        </Panel>
      )}
      {section === "usage" && (
        <Panel
          title={
            subsection === "ledger"
              ? "Append-only usage ledger"
              : subsection === "models"
                ? "Usage by model"
                : "Quota status"
          }
        >
          <UsageManagement subsection={subsection} />
        </Panel>
      )}
      {section === "content" && (
        <Panel title="Content library">
          <ContentManagement subsection={subsection} />
        </Panel>
      )}
      {!special &&
        section !== "dashboard" &&
        section !== "usage" &&
        section !== "content" &&
        section !== "team" &&
        section !== "billing" &&
        section !== "credits" &&
        section !== "settings" &&
        section !== "admin" && (
          <Panel title={section === "admin" ? "Service health" : "Recent activity"}>
            <DataRows rows={base.rows ?? []} />
          </Panel>
        )}
      {(section === "dashboard" || (section === "usage" && !subsection)) && (
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
