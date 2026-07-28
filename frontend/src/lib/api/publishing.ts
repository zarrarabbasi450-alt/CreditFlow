import { request } from "./client";
import type {
  ConnectLinkedInResponse,
  DevLinkedInConnectionRequest,
  ProductView,
  Publication,
  PublishContentRequest,
  PublishingCollection,
  PublishRequest,
  SocialConnection,
} from "@/types";

interface RawSocialConnection {
  id: string;
  account_id: string;
  provider: "linkedin";
  profile_name: string;
  profile_urn?: string | null;
  status: SocialConnection["status"];
  connected_at?: string | null;
}

interface RawPublishJob {
  id: string;
  account_id: string;
  content_id: string;
  scheduled_post_id?: string | null;
  connection_id?: string | null;
  status: Publication["status"];
  caption: string;
  image_url?: string | null;
  linkedin_post_id?: string | null;
  linkedin_post_url?: string | null;
  failure_reason?: string | null;
  attempts: number;
  created_at: string;
  published_at?: string | null;
}

const toConnection = (connection: RawSocialConnection): SocialConnection => ({
  id: connection.id,
  accountId: connection.account_id,
  provider: connection.provider,
  profileName: connection.profile_name,
  profileUrn: connection.profile_urn ?? null,
  status: connection.status,
  connectedAt: connection.connected_at ?? null,
});

const toPublication = (job: RawPublishJob): Publication => ({
  id: job.id,
  accountId: job.account_id,
  contentId: job.content_id,
  scheduledPostId: job.scheduled_post_id ?? null,
  connectionId: job.connection_id ?? null,
  status: job.status,
  caption: job.caption,
  imageUrl: job.image_url ?? null,
  linkedinPostId: job.linkedin_post_id ?? null,
  linkedinPostUrl: job.linkedin_post_url ?? null,
  failureReason: job.failure_reason ?? null,
  attempts: job.attempts,
  createdAt: job.created_at,
  publishedAt: job.published_at ?? null,
});

const toPublishPayload = (data: PublishRequest) => ({
  connection_id: data.connectionId ?? null,
  caption: data.caption,
  image_url: data.imageUrl ?? null,
  image_asset_ref: data.imageAssetRef ?? null,
});

const toPublishContentPayload = (data: PublishContentRequest) => ({
  content_id: data.contentId,
  connection_id: data.connectionId ?? null,
  caption: data.caption ?? null,
});

export const getPublishing = async (): Promise<PublishingCollection> => {
  const response = await request<{ view: ProductView; connections: RawSocialConnection[]; jobs: RawPublishJob[] }>({
    url: "/publishing",
    method: "GET",
  });
  return {
    view: response.view,
    connections: response.connections.map(toConnection),
    jobs: response.jobs.map(toPublication),
  };
};

export const connectLinkedIn = async () => {
  const response = await request<{ authorization_url: string; state: string }>({
    url: "/publishing/linkedin/connect",
    method: "POST",
  });
  return { authorizationUrl: response.authorization_url, state: response.state } satisfies ConnectLinkedInResponse;
};

export const connectLinkedInDev = (data: DevLinkedInConnectionRequest) =>
  request<RawSocialConnection>({
    url: "/publishing/linkedin/dev-connect",
    method: "POST",
    data: { profile_name: data.profileName, profile_url: data.profileUrl },
  }).then(toConnection);

export const disconnectLinkedIn = (connectionId: string) =>
  request<{ message: string }>({ url: `/publishing/connections/${connectionId}`, method: "DELETE" });

export const publishToLinkedIn = (data: PublishRequest) =>
  request<RawPublishJob>({ url: "/publishing/linkedin", method: "POST", data: toPublishPayload(data) }).then(
    toPublication,
  );

export const publishContentToLinkedIn = (data: PublishContentRequest) =>
  request<RawPublishJob>({
    url: "/publishing/linkedin/content",
    method: "POST",
    data: toPublishContentPayload(data),
  }).then(toPublication);

export const refreshLinkedInTokens = () =>
  request<{ refreshed: number }>({ url: "/publishing/linkedin/refresh-tokens", method: "POST" });
