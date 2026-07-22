export type ContentStatus = "draft" | "approved" | "published";
export type ContentType = "post" | "article" | "campaign_brief" | "carousel";

export interface ContentItem {
  id: string;
  accountId: string;
  createdBy: string;
  title: string;
  body: string;
  contentType: ContentType;
  status: ContentStatus;
  imageUrl?: string | null;
  imageAssetRef?: string | null;
  sourceGenerationId?: string | null;
  createdAt: string;
  updatedAt: string;
  publishedAt?: string | null;
  version: number;
}
export interface GenerationRequest {
  prompt: string;
  model: "fast" | "quality";
  generateImage?: boolean;
  estimatedTokens?: number;
}
export interface GenerationChunk {
  type: "token" | "complete" | "failed" | "cancelled";
  value: string;
  generationId: string;
  imageUrl?: string | null;
}

export interface GenerationStart {
  jobId: string;
  channel: string;
  model: string;
  status: string;
  imageUrl?: string | null;
}

export interface GenerationJob {
  id: string;
  accountId: string;
  userId: string;
  model: string;
  status: string;
  prompt: string;
  response: string;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  costMicrousd: number;
  errorReason?: string | null;
  createdAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
}

export interface PromptHistory {
  id: string;
  jobId: string;
  model: string;
  prompt: string;
  response: string;
  totalTokens: number;
  costMicrousd: number;
  createdAt: string;
}

export interface ImageGeneration {
  id: string;
  imageUrl: string;
  status: string;
}
