import { useQuery } from "@tanstack/react-query";
import { getPromptHistory } from "@/lib/api/content";

export const usePromptHistory = (enabled = true) =>
  useQuery({ queryKey: ["ai", "history"], queryFn: getPromptHistory, enabled });
