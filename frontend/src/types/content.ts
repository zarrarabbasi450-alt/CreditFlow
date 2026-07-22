export interface ContentItem {
  id: string;
  accountId: string;
  title: string;
  type: "LinkedIn post" | "Campaign brief" | "Article" | "LinkedIn carousel";
  owner: string;
  status: "Draft" | "Review" | "Approved" | "Scheduled";
  tags: string[];
  updatedAt: string;
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
