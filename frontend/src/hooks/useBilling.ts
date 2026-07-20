import { useQuery } from "@tanstack/react-query";
import { getBilling } from "@/lib/api/billing";
export const useBilling = () => useQuery({ queryKey: ["billing"], queryFn: getBilling });
