"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getCurrentAccount, updateAccount } from "@/lib/api/tenants";

export function AccountSettings({ subsection }: { subsection?: string }) {
  const queryClient = useQueryClient();
  const account = useQuery({ queryKey: ["selected-account"], queryFn: getCurrentAccount });
  const [name, setName] = useState("");
  useEffect(() => setName(account.data?.name ?? ""), [account.data?.name]);
  const save = useMutation({
    mutationFn: () => updateAccount(account.data!.id, name),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["selected-account"] });
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
      await queryClient.invalidateQueries({ queryKey: ["product-view", "settings"] });
    },
  });
  if (account.isLoading) return <p>Loading account…</p>;
  if (account.error || !account.data)
    return <p className="team-error">{account.error?.message ?? "Unable to load account"}</p>;
  if (subsection === "sessions")
    return (
      <div className="admin-empty">
        <strong>Current session is active</strong>
        <p>Use Sign out in the sidebar to revoke the current access and refresh tokens.</p>
      </div>
    );
  if (subsection === "api-keys")
    return (
      <div className="admin-empty">
        <strong>No API keys</strong>
        <p>API-key issuance is not part of the completed Auth Service contract.</p>
      </div>
    );
  return (
    <form
      className="generator"
      onSubmit={(event) => {
        event.preventDefault();
        if (name.trim()) save.mutate();
      }}
    >
      <label htmlFor="account-name">Account name</label>
      <input id="account-name" value={name} onChange={(event) => setName(event.target.value)} required />
      <label htmlFor="account-slug">Account slug</label>
      <input id="account-slug" value={account.data.slug} disabled />
      <button className="primary-button" disabled={save.isPending || name.trim() === account.data.name}>
        {save.isPending ? "Saving…" : "Save changes"}
      </button>
      {save.isSuccess && <p className="team-feedback">Account settings saved.</p>}
      {save.error && <p className="team-error">{save.error.message}</p>}
    </form>
  );
}
