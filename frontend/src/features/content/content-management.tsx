"use client";

import { ArrowLeft, CheckCircle2, Image as ImageIcon, Send, Trash2 } from "lucide-react";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { useToast } from "@/components/toast";
import { useAuth } from "@/hooks/useAuth";
import { useContent, useContentMutations } from "@/hooks/useContent";
import type { ContentStatus, ContentType } from "@/types";

const statusLabels: Record<ContentStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  published: "Published",
};

const typeLabels: Record<ContentType, string> = {
  post: "Post",
  article: "Article",
  campaign_brief: "Campaign brief",
  carousel: "Carousel",
};

function canPublish(role?: string | null) {
  return role === "Owner" || role === "Admin" || role === "SuperAdmin";
}

export function ContentManagement({ subsection }: { subsection?: string }) {
  const { data, isLoading, error } = useContent();
  const mutations = useContentMutations();
  const { notify } = useToast();
  const { user } = useAuth();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [contentType, setContentType] = useState<ContentType>("post");
  const [feedback, setFeedback] = useState<string | null>(null);
  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const selected = selectedId ? (items.find((item) => item.id === selectedId) ?? null) : null;
  const allowedToPublish = canPublish(user?.role ?? user?.accountRole);
  const filter = subsection === "drafts" || subsection === "approved" || subsection === "published" ? subsection : null;
  const visibleItems = useMemo(
    () => (filter ? items.filter((item) => item.status === filter) : items),
    [filter, items],
  );

  useEffect(() => {
    if (!selected) return;
    setSelectedId(selected.id);
    setTitle(selected.title);
    setBody(selected.body);
    setContentType(selected.contentType);
  }, [selected]);

  function startNewDraft() {
    setSelectedId(null);
    setTitle("");
    setBody("");
    setContentType("post");
    setFeedback(null);
    document.getElementById("content-title")?.focus();
  }

  useEffect(() => {
    window.addEventListener("content:new-draft", startNewDraft);
    return () => window.removeEventListener("content:new-draft", startNewDraft);
  }, []);

  const busy =
    mutations.create.isPending ||
    mutations.update.isPending ||
    mutations.remove.isPending ||
    mutations.approve.isPending ||
    mutations.publish.isPending ||
    mutations.uploadImage.isPending;

  async function saveDraft() {
    if (!title.trim() || !body.trim()) return;
    setFeedback(null);
    try {
      if (selected) {
        await mutations.update.mutateAsync({ id: selected.id, payload: { title, body } });
        setFeedback("Draft updated and versioned.");
        notify("Content updated");
      } else {
        const created = await mutations.create.mutateAsync({ title, body, contentType });
        setSelectedId(created.id);
        setFeedback("Draft created.");
        notify("Content created");
      }
    } catch (saveError) {
      notify(saveError instanceof Error ? saveError.message : "Unable to save content");
    }
  }

  async function approve() {
    if (!selected) return;
    try {
      await mutations.approve.mutateAsync(selected.id);
      notify("Content approved");
    } catch (approveError) {
      notify(approveError instanceof Error ? approveError.message : "Unable to approve content");
    }
  }

  async function publish() {
    if (!selected) return;
    try {
      await mutations.publish.mutateAsync(selected.id);
      notify("Content published");
    } catch (publishError) {
      notify(publishError instanceof Error ? publishError.message : "Unable to publish content");
    }
  }

  async function remove() {
    if (!selected) return;
    try {
      await mutations.remove.mutateAsync(selected.id);
      setSelectedId(null);
      setTitle("");
      setBody("");
      notify("Content deleted");
    } catch (deleteError) {
      notify(deleteError instanceof Error ? deleteError.message : "Unable to delete content");
    }
  }

  async function uploadImage(file?: File) {
    if (!selected || !file) return;
    try {
      await mutations.uploadImage.mutateAsync({ id: selected.id, file });
      notify("Image attached");
    } catch (uploadError) {
      notify(uploadError instanceof Error ? uploadError.message : "Unable to upload image");
    }
  }

  if (isLoading) return <p className="content-state">Loading content…</p>;
  if (error) return <p className="content-state error">Unable to load content.</p>;

  return (
    <div className="content-management">
      <aside className="content-library">
        <div className="content-library-header">
          <strong>Library</strong>
          {selected && (
            <button type="button" className="content-library-back" onClick={startNewDraft}>
              <ArrowLeft />
              Back
            </button>
          )}
        </div>
        {visibleItems.length === 0 && <p>No {filter ?? "content"} items yet.</p>}
        {visibleItems.map((item) => (
          <button
            key={item.id}
            type="button"
            className={selected?.id === item.id ? "active" : undefined}
            onClick={() => setSelectedId(item.id)}
          >
            <span>{statusLabels[item.status]}</span>
            <strong>{item.title}</strong>
            <small>
              {typeLabels[item.contentType]} · v{item.version} · {new Date(item.updatedAt).toLocaleDateString()}
            </small>
          </button>
        ))}
      </aside>
      <section className="content-editor">
        <div className="content-editor-grid">
          <label>
            Title
            <input
              id="content-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="LinkedIn launch post"
              disabled={selected?.status === "published"}
            />
          </label>
          <label>
            Type
            <select
              value={contentType}
              onChange={(event) => setContentType(event.target.value as ContentType)}
              disabled={Boolean(selected)}
            >
              {Object.entries(typeLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="content-body">
            Body
            <textarea
              rows={12}
              value={body}
              onChange={(event) => setBody(event.target.value)}
              placeholder="Write or paste the generated content here…"
              disabled={selected?.status === "published"}
            />
          </label>
        </div>
        {selected?.imageUrl && (
          <a className="content-image-preview" href={selected.imageUrl} target="_blank" rel="noreferrer">
            <Image src={selected.imageUrl} alt={selected.title} width={620} height={320} unoptimized />
            <span>Open attached image</span>
          </a>
        )}
        <div className="content-actions">
          <button className="primary-button" type="button" disabled={busy || selected?.status === "published"} onClick={saveDraft}>
            {selected ? "Save version" : "Create draft"}
          </button>
          <label className={`secondary-button ${!selected || selected.status === "published" ? "disabled" : ""}`}>
            <ImageIcon />
            Upload image
            <input
              type="file"
              accept="image/*"
              disabled={!selected || selected.status === "published"}
              onChange={(event) => void uploadImage(event.target.files?.[0])}
            />
          </label>
          <button
            className="secondary-button"
            type="button"
            disabled={busy || !selected || selected.status !== "draft"}
            onClick={approve}
          >
            <CheckCircle2 />
            Approve
          </button>
          <button
            className="secondary-button"
            type="button"
            disabled={busy || !selected || selected.status !== "approved" || !allowedToPublish}
            onClick={publish}
            title={allowedToPublish ? undefined : "Owner or Admin permission is required"}
          >
            <Send />
            Publish
          </button>
          <button
            className="secondary-button danger"
            type="button"
            disabled={busy || !selected || selected.status === "published"}
            onClick={remove}
          >
            <Trash2 />
            Delete
          </button>
        </div>
        {feedback && <p className="content-feedback">{feedback}</p>}
        {selected?.status === "published" && <p className="content-feedback">Published content is locked.</p>}
      </section>
    </div>
  );
}
