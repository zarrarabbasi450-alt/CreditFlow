"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createAccount, listAccounts, selectedAccountStore } from "@/lib/api/tenants";
import { useAuth } from "@/hooks/useAuth";

const slugify = (name: string) =>
  name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");

export function WorkspaceSwitcher() {
  const queryClient = useQueryClient();
  const { switchAccount } = useAuth();
  const container = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const { data: accounts = [], isLoading } = useQuery({ queryKey: ["accounts"], queryFn: listAccounts });
  const selectedId = selectedAccountStore.get();
  const selected = accounts.find(({ id }) => id === selectedId) ?? accounts[0];
  const create = useMutation({
    mutationFn: (workspaceName: string) =>
      createAccount({ name: workspaceName, slug: slugify(workspaceName), type: "team" }),
    onSuccess: async (account) => {
      await switchAccount(account.id);
      selectedAccountStore.set(account.id);
      setName("");
      setCreating(false);
      setOpen(false);
      await queryClient.invalidateQueries();
    },
  });

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const select = async (accountId: string) => {
    if (accountId !== selected?.id) await switchAccount(accountId);
    selectedAccountStore.set(accountId);
    setOpen(false);
    await queryClient.invalidateQueries();
  };

  return (
    <div className="workspace-switcher" ref={container}>
      <button className="workspace" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        <span>{selected?.name.slice(0, 2).toUpperCase() ?? "CF"}</span>
        <div>
          <small>Workspace</small>
          <strong>{isLoading ? "Loading…" : (selected?.name ?? "No workspace")}</strong>
        </div>
        <ChevronDown />
      </button>
      {open && (
        <div className="workspace-menu">
          <small>Your workspaces</small>
          {accounts.map((account) => (
            <button key={account.id} onClick={() => void select(account.id)}>
              <span>{account.name.slice(0, 2).toUpperCase()}</span>
              <div>
                <strong>{account.name}</strong>
                <small>
                  {account.type} · {account.plan_tier}
                </small>
              </div>
              {account.id === selected?.id && <Check />}
            </button>
          ))}
          {creating ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                if (name.trim()) create.mutate(name.trim());
              }}
            >
              <input
                autoFocus
                aria-label="Workspace name"
                placeholder="Team workspace name"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <button disabled={create.isPending || slugify(name).length < 2}>Create</button>
              {create.error && <p>{create.error.message}</p>}
            </form>
          ) : (
            <button className="workspace-create" onClick={() => setCreating(true)}>
              <Plus /> Create team workspace
            </button>
          )}
        </div>
      )}
    </div>
  );
}
