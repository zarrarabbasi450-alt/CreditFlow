import { request } from "./client";
import type {
  ContentItem,
  GenerationChunk,
  GenerationJob,
  GenerationRequest,
  GenerationStart,
  ImageGeneration,
  ProductView,
  PromptHistory,
} from "@/types";

interface RawGenerationStart {
  job_id: string;
  channel: string;
  model: string;
  status: string;
  image_url?: string | null;
}

interface RawGenerationJob {
  id: string;
  account_id: string;
  user_id: string;
  model: string;
  status: string;
  prompt: string;
  response: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_microusd: number;
  error_reason?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

interface RawPromptHistory {
  id: string;
  job_id: string;
  model: string;
  prompt: string;
  response: string | null;
  total_tokens: number;
  cost_microusd: number;
  created_at: string;
}

interface RawImageGeneration {
  id: string;
  image_url: string;
  status: string;
}

const toGenerationStart = (value: RawGenerationStart): GenerationStart => ({
  jobId: value.job_id,
  channel: value.channel,
  model: value.model,
  status: value.status,
  imageUrl: value.image_url ?? null,
});

const toGenerationJob = (value: RawGenerationJob): GenerationJob => ({
  id: value.id,
  accountId: value.account_id,
  userId: value.user_id,
  model: value.model,
  status: value.status,
  prompt: value.prompt,
  response: value.response ?? "",
  promptTokens: value.prompt_tokens,
  completionTokens: value.completion_tokens,
  totalTokens: value.total_tokens,
  costMicrousd: value.cost_microusd,
  errorReason: value.error_reason ?? null,
  createdAt: value.created_at,
  startedAt: value.started_at ?? null,
  completedAt: value.completed_at ?? null,
});

const toPromptHistory = (value: RawPromptHistory): PromptHistory => ({
  id: value.id,
  jobId: value.job_id,
  model: value.model,
  prompt: value.prompt,
  response: value.response ?? "",
  totalTokens: value.total_tokens,
  costMicrousd: value.cost_microusd,
  createdAt: value.created_at,
});

const toImageGeneration = (value: RawImageGeneration): ImageGeneration => ({
  id: value.id,
  imageUrl: value.image_url,
  status: value.status,
});

const toGenerationPayload = (payload: GenerationRequest) => ({
  prompt: payload.prompt,
  model: payload.model,
  generate_image: payload.generateImage ?? false,
  estimated_tokens: payload.estimatedTokens,
});

export const getContent = () =>
  request<{ view: ProductView; items: ContentItem[] }>({ url: "/content", method: "GET" });
export const getAiOverview = () => request<ProductView>({ url: "/ai/overview", method: "GET" });
export const getPromptHistory = async () =>
  (await request<RawPromptHistory[]>({ url: "/ai/history", method: "GET" })).map(toPromptHistory);
export const getGeneration = (jobId: string) =>
  request<RawGenerationJob>({ url: `/ai/generations/${jobId}`, method: "GET" }).then(toGenerationJob);
export const cancelGeneration = (jobId: string) =>
  request<{ status: string }>({ url: `/ai/generations/${jobId}/cancel`, method: "POST" });
export const generateImage = (prompt: string) =>
  request<RawImageGeneration>({ url: "/ai/images", method: "POST", data: { prompt } }).then(
    toImageGeneration,
  );

const sleep = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));

export async function* streamGeneration(payload: GenerationRequest): AsyncGenerator<GenerationChunk> {
  const result = toGenerationStart(
    await request<RawGenerationStart>({
      url: "/ai/generations",
      method: "POST",
      data: toGenerationPayload(payload),
    }),
  );
  yield { type: "token", value: "Generation started. Waiting for OpenRouter...\n\n", generationId: result.jobId };

  let job: GenerationJob | null = null;
  for (let attempt = 0; attempt < 90; attempt += 1) {
    job = await getGeneration(result.jobId);
    if (["completed", "failed", "cancelled"].includes(job.status)) break;
    await sleep(1000);
  }

  if (!job || !["completed", "failed", "cancelled"].includes(job.status)) {
    yield {
      type: "failed",
      value: "Generation is still running. Please refresh prompt history in a moment.",
      generationId: result.jobId,
    };
    return;
  }

  if (job.status === "failed") {
    yield {
      type: "failed",
      value: job.errorReason ?? "Generation failed",
      generationId: result.jobId,
    };
    return;
  }

  if (job.status === "cancelled") {
    yield { type: "cancelled", value: "Generation cancelled", generationId: result.jobId };
    return;
  }

  for (const token of job.response.match(/\S+\s*/g) ?? []) {
    await sleep(18);
    yield { type: "token", value: token, generationId: result.jobId };
  }
  yield { type: "complete", value: job.response, generationId: result.jobId, imageUrl: result.imageUrl };
}
