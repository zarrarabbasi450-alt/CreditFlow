import { useQuery } from "@tanstack/react-query";
import { getUsage } from "@/lib/api/usage";
export const useUsage = () => useQuery({ queryKey: ["usage"], queryFn: getUsage });
