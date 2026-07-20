import { useQuery } from "@tanstack/react-query";
import { getCredits } from "@/lib/api/credits";
export const useCredits = () => useQuery({ queryKey: ["credits"], queryFn: getCredits });
