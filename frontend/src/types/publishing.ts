export interface SocialConnection {
  id: string;
  accountId: string;
  provider: "linkedin";
  profileName: string;
  status: "Connected" | "Expired";
  connectedAt: string;
}
export interface PublishRequest {
  accountId: string;
  connectionId: string;
  caption: string;
  image?: File;
}
export interface Publication {
  id: string;
  provider: "linkedin";
  status: "Queued" | "Published" | "Failed";
  providerPostId?: string;
  createdAt: string;
}
