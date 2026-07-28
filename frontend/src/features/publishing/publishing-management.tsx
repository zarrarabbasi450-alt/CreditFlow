"use client";

import { ExternalLink, Link2, RefreshCcw, Send, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useToast } from "@/components/toast";
import { useContent } from "@/hooks/useContent";
import { usePublishing, usePublishingMutations } from "@/hooks/usePublishing";
import type { Publication, SocialConnection } from "@/types";

function statusLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function activeConnection(connections: SocialConnection[]) {
  return connections.find((connection) => connection.status === "connected") ?? null;
}

function jobTone(job: Publication) {
  if (job.status === "published") return "success";
  if (job.status === "failed" || job.status === "dead_letter") return "danger";
  return "muted";
}

export function PublishingManagement({ subsection }: { subsection?: string }) {
  const { notify } = useToast();
  const publishing = usePublishing();
  const content = useContent();
  const mutations = usePublishingMutations();
  const [caption, setCaption] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [contentId, setContentId] = useState("");
  const [contentCaption, setContentCaption] = useState("");

  const connections = publishing.data?.connections ?? [];
  const jobs = publishing.data?.jobs ?? [];
  const connected = activeConnection(connections);
  const approvedContent = useMemo(
    () => (content.data?.items ?? []).filter((item) => item.status === "approved" || item.status === "published"),
    [content.data?.items],
  );
  const busy =
    mutations.connect.isPending ||
    mutations.disconnect.isPending ||
    mutations.publishManual.isPending ||
    mutations.publishContent.isPending ||
    mutations.refreshTokens.isPending;

  async function startOAuth() {
    try {
      const result = await mutations.connect.mutateAsync();
      window.location.assign(result.authorizationUrl);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Unable to start LinkedIn OAuth");
    }
  }

  async function disconnect(connection: SocialConnection) {
    try {
      await mutations.disconnect.mutateAsync(connection.id);
      notify("LinkedIn connection revoked");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Unable to disconnect LinkedIn");
    }
  }

  async function publishManual() {
    if (!caption.trim()) {
      notify("Write a caption before publishing.");
      return;
    }
    try {
      await mutations.publishManual.mutateAsync({
        connectionId: connected?.id,
        caption,
        imageUrl: imageUrl.trim() || null,
      });
      setCaption("");
      setImageUrl("");
      notify("LinkedIn publish job completed");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Unable to publish to LinkedIn");
    }
  }

  async function publishContent() {
    if (!contentId) {
      notify("Select approved content first.");
      return;
    }
    try {
      await mutations.publishContent.mutateAsync({
        contentId,
        connectionId: connected?.id,
        caption: contentCaption.trim() || null,
      });
      setContentId("");
      setContentCaption("");
      notify("Content published to LinkedIn");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Unable to publish selected content");
    }
  }

  async function refreshTokens() {
    try {
      const result = await mutations.refreshTokens.mutateAsync();
      notify(`Refreshed ${result.refreshed} LinkedIn token(s)`);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Unable to refresh LinkedIn tokens");
    }
  }

  if (publishing.isLoading) return <p className="publishing-state">Loading publishing settings...</p>;
  if (publishing.error) return <p className="publishing-state error">Unable to load publishing service.</p>;

  if (subsection === "linkedin") {
    return (
      <div className="publishing-management">
        {!connected && (
          <div className="publishing-grid single">
            <article>
              <span>Production OAuth</span>
              <h3>Connect real LinkedIn</h3>
              <p>
                Uses LinkedIn OpenID Connect and Share on LinkedIn scopes. Access and refresh tokens are encrypted before
                storage.
              </p>
              <button className="primary-button" type="button" disabled={busy} onClick={() => void startOAuth()}>
                <Link2 />
                Connect with LinkedIn
              </button>
            </article>
          </div>
        )}
        {connected && (
          <p className="publishing-warning">
            A LinkedIn account is already connected. Disconnect it before connecting another.
          </p>
        )}
        <ConnectionList
          connections={connections}
          busy={busy}
          onDisconnect={(connection) => void disconnect(connection)}
          onRefresh={() => void refreshTokens()}
        />
      </div>
    );
  }

  if (subsection === "linkedin-image") {
    return (
      <div className="publishing-management">
        <div className="publishing-grid single">
          <article>
            <span>Image post</span>
            <h3>Publish text + image to LinkedIn</h3>
            <p>
              The service registers the image with LinkedIn, uploads the binary to LinkedIn&apos;s upload URL, then publishes
              the post with the resulting asset URN.
            </p>
            <label>
              Caption
              <textarea
                rows={6}
                value={caption}
                onChange={(event) => setCaption(event.target.value)}
                placeholder="Share your launch update..."
              />
            </label>
            <label>
              Image URL
              <input
                value={imageUrl}
                onChange={(event) => setImageUrl(event.target.value)}
                placeholder="https://..."
              />
            </label>
            <button className="primary-button" type="button" disabled={busy || !connected} onClick={() => void publishManual()}>
              <Send />
              Publish image post
            </button>
            {!connected && <p className="publishing-warning">Connect LinkedIn before publishing.</p>}
          </article>
        </div>
      </div>
    );
  }

  if (subsection === "history") {
    return (
      <div className="publishing-management">
        <JobList jobs={jobs} />
      </div>
    );
  }

  return (
    <div className="publishing-management">
      <div className="publishing-summary-grid">
        <article>
          <span>Connected profiles</span>
          <strong>{connections.filter((connection) => connection.status === "connected").length}</strong>
          <small>LinkedIn OAuth or local dev profiles</small>
        </article>
        <article>
          <span>Published posts</span>
          <strong>{jobs.filter((job) => job.status === "published").length}</strong>
          <small>Successful LinkedIn jobs</small>
        </article>
        <article>
          <span>Failed jobs</span>
          <strong>{jobs.filter((job) => job.status === "failed" || job.status === "dead_letter").length}</strong>
          <small>Retry or inspect before scheduling again</small>
        </article>
      </div>
      <div className="publishing-grid single">
        <article>
          <span>Approved content</span>
          <h3>Publish an existing content item</h3>
          <p>Choose approved content from the Content Service and publish it to the connected LinkedIn profile.</p>
          <label>
            Content item
            <select value={contentId} onChange={(event) => setContentId(event.target.value)}>
              <option value="">Select approved content</option>
              {approvedContent.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title} · {statusLabel(item.status)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Optional caption override
            <textarea
              rows={4}
              value={contentCaption}
              onChange={(event) => setContentCaption(event.target.value)}
              placeholder="Leave empty to use the content body."
            />
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={busy || !connected || !contentId}
            onClick={() => void publishContent()}
          >
            <Send />
            Publish selected content
          </button>
          {!connected && <p className="publishing-warning">Connect LinkedIn before publishing.</p>}
        </article>
      </div>
      <JobList jobs={jobs.slice(0, 5)} />
    </div>
  );
}

function ConnectionList({
  connections,
  busy,
  onDisconnect,
  onRefresh,
}: {
  connections: SocialConnection[];
  busy: boolean;
  onDisconnect: (connection: SocialConnection) => void;
  onRefresh: () => void;
}) {
  return (
    <div className="publishing-list">
      <div className="publishing-list-title">
        <h3>LinkedIn connections</h3>
        <button className="secondary-button" type="button" disabled={busy} onClick={onRefresh}>
          <RefreshCcw />
          Refresh tokens
        </button>
      </div>
      {connections.length === 0 && <p>No LinkedIn profiles connected yet.</p>}
      {connections.map((connection) => (
        <div key={connection.id}>
          <div>
            <strong>{connection.profileName}</strong>
            <small>
              {statusLabel(connection.status)} · {connection.connectedAt ? new Date(connection.connectedAt).toLocaleString() : "Pending"}
            </small>
            {connection.profileUrn?.startsWith("dev:") ? (
              <a href={connection.profileUrn.replace("dev:", "")} target="_blank" rel="noreferrer">
                Open profile <ExternalLink />
              </a>
            ) : null}
          </div>
          {connection.status === "connected" && (
            <button className="secondary-button danger" type="button" disabled={busy} onClick={() => onDisconnect(connection)}>
              <Trash2 />
              Disconnect
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

function JobList({ jobs }: { jobs: Publication[] }) {
  return (
    <div className="publishing-list">
      <div className="publishing-list-title">
        <h3>Publish history</h3>
      </div>
      {jobs.length === 0 && <p>No publish jobs yet.</p>}
      {jobs.map((job) => (
        <div key={job.id}>
          <div>
            <strong>{job.caption}</strong>
            <small>
              {statusLabel(job.status)} · attempts {job.attempts} · {new Date(job.createdAt).toLocaleString()}
            </small>
            {job.failureReason ? <em className="danger">{job.failureReason}</em> : null}
            {job.linkedinPostUrl ? (
              <a href={job.linkedinPostUrl} target="_blank" rel="noreferrer">
                Open LinkedIn post <ExternalLink />
              </a>
            ) : null}
          </div>
          <em className={jobTone(job)}>{statusLabel(job.status)}</em>
        </div>
      ))}
    </div>
  );
}
