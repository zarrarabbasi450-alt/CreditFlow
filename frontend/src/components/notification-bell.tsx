"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Bell, CheckCircle2, Clock3 } from "lucide-react";
import { getNotifications } from "@/lib/api/notifications";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["notifications", "bell"],
    queryFn: getNotifications,
    refetchInterval: 30000,
  });
  const items = data?.items ?? [];
  const unreadCount = items.filter((item) => item.status === "Unread").length;

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setOpen(false);
    }
    function onEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onEscape);
    };
  }, []);

  return (
    <div className="notification-bell" ref={containerRef}>
      <button
        className="icon-button"
        aria-label="Notifications"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Bell />
        {unreadCount > 0 && <i />}
      </button>
      {open && (
        <div className="notification-dropdown" role="menu" aria-label="Notifications">
          <div className="notification-dropdown-header">
            <strong>Notifications</strong>
            {unreadCount > 0 && <span>{unreadCount} unread</span>}
          </div>
          <div className="notification-dropdown-list">
            {isLoading && <p className="notification-dropdown-empty">Loading…</p>}
            {!isLoading && items.length === 0 && (
              <p className="notification-dropdown-empty">No notifications yet.</p>
            )}
            {items.slice(0, 8).map((item) => (
              <div key={item.id} className={item.status === "Unread" ? "unread" : undefined}>
                <span className="row-icon">
                  {item.category === "Publishing" ? <Clock3 /> : <CheckCircle2 />}
                </span>
                <div>
                  <strong>{item.title}</strong>
                  <small>{item.detail}</small>
                </div>
                <em>{new Date(item.createdAt).toLocaleDateString()}</em>
              </div>
            ))}
          </div>
          <Link href="/notifications" className="notification-dropdown-footer" onClick={() => setOpen(false)}>
            View all notifications
          </Link>
        </div>
      )}
    </div>
  );
}
