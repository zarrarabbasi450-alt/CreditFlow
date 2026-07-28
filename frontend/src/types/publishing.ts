export interface SocialConnection {
  id: string;
  accountId: string;
  provider: "linkedin";
  profileName: string;
  profileUrn?: string | null;
  status: "pending" | "connected" | "expired" | "revoked" | "failed";
  connectedAt?: string | null;
}
export interface PublishRequest {
  connectionId?: string | null;
  caption: string;
  imageUrl?: string | null;
  imageAssetRef?: string | null;
}
export interface PublishContentRequest {
  contentId: string;
  connectionId?: string | null;
  caption?: string | null;
}
export interface Publication {
  id: string;
  accountId: string;
  contentId: string;
  scheduledPostId?: string | null;
  connectionId?: string | null;
  status: "queued" | "publishing" | "published" | "failed" | "dead_letter";
  caption: string;
  imageUrl?: string | null;
  linkedinPostId?: string | null;
  linkedinPostUrl?: string | null;
  failureReason?: string | null;
  attempts: number;
  createdAt: string;
  publishedAt?: string | null;
}
export interface PublishingCollection {
  view: import("./api").ProductView;
  connections: SocialConnection[];
  jobs: Publication[];
}
export interface ConnectLinkedInResponse {
  authorizationUrl: string;
  state: string;
}
export interface DevLinkedInConnectionRequest {
  profileName: string;
  profileUrl: string;
}
