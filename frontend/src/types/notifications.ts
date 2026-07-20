export interface Notification {
  id: string;
  accountId: string;
  title: string;
  detail: string;
  category: "Publishing" | "Credits" | "Scraper" | "Account";
  status: "Read" | "Unread";
  createdAt: string;
}
export interface NotificationPreferences {
  email: boolean;
  inApp: boolean;
  publishing: boolean;
  lowBalance: boolean;
}
