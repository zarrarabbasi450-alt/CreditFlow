import { useQuery } from "@tanstack/react-query";
import { getContent } from "@/lib/api/content";
export const useContent = () => useQuery({ queryKey: ["content"], queryFn: getContent });
