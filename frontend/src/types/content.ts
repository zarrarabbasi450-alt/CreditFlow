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
  model: string;
  accountId: string;
}
export interface GenerationChunk {
  type: "token" | "complete";
  value: string;
  generationId: string;
}
