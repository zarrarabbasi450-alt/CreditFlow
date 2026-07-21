import { useQuery } from "@tanstack/react-query";
import { getUsage, getUsageLedger } from "@/lib/api/usage";
export const useUsage = () => useQuery({ queryKey: ["usage"], queryFn: getUsage });
export const useUsageLedger = (enabled = true) =>
  useQuery({ queryKey: ["usage", "ledger"], queryFn: getUsageLedger, enabled });
