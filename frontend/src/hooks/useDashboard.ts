import { useQuery } from "@tanstack/react-query";
import { getDashboard } from "@/lib/api/dashboard";
export const useDashboard = () => useQuery({ queryKey: ["dashboard"], queryFn: getDashboard });
