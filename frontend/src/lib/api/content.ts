import { request } from "./client";
import type { ContentItem, GenerationChunk, ProductView } from "@/types";
export const getContent = () =>
  request<{ view: ProductView; items: ContentItem[] }>({ url: "/content", method: "GET" });
export const getAiOverview = () => request<ProductView>({ url: "/ai/overview", method: "GET" });
export async function* streamGeneration(prompt: string): AsyncGenerator<GenerationChunk> {
  const result = await request<{ generationId: string; tokens: string[] }>({
    url: "/ai/generations",
    method: "POST",
    data: { prompt, model: "claude-3-7-sonnet" },
  });
  for (const token of result.tokens) {
    await new Promise((resolve) => setTimeout(resolve, 30));
    yield { type: "token", value: `${token} `, generationId: result.generationId };
  }
  yield { type: "complete", value: "", generationId: result.generationId };
}
