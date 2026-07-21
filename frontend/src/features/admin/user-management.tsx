"use client";

import { useEffect, useState } from "react";
import * as adminApi from "@/lib/api/admin";
import type { AdminUser } from "@/types";

export function AdminUserManagement() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    adminApi
      .listUsers()
      .then(setUsers)
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Unable to load users");
      });
  }, []);

  async function changeRole(userId: string, value: string) {
    try {
      const updated = await adminApi.updatePlatformRole(userId, value === "SuperAdmin" ? "SuperAdmin" : null);
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update role");
    }
  }

  return (
    <div className="data-rows">
      {error && <p className="form-error">{error}</p>}
      {users.map((item) => (
        <div key={item.id}>
          <div>
            <strong>{item.email}</strong>
            <small>{item.isActive ? "Active user" : "Inactive user"}</small>
          </div>
          <select
            aria-label={`Platform role for ${item.email}`}
            value={item.platformRole ?? "User"}
            onChange={(event) => void changeRole(item.id, event.target.value)}
          >
            <option value="User">User</option>
            <option value="SuperAdmin">SuperAdmin</option>
          </select>
        </div>
      ))}
    </div>
  );
}
