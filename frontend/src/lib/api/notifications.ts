import { request } from "./client";
import type { Notification, NotificationPreferences, ProductView } from "@/types";
export const getNotifications = () =>
  request<{ view: ProductView; items: Notification[] }>({ url: "/notifications", method: "GET" });
export const updateNotificationPreferences = (data: NotificationPreferences) =>
  request<NotificationPreferences>({ url: "/notifications/preferences", method: "PUT", data });
