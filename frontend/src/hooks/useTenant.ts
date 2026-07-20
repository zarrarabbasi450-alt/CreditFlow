import { useQuery } from "@tanstack/react-query";
import { getTenantOverview } from "@/lib/api/tenants";
export const useTenant = () => useQuery({ queryKey: ["tenant"], queryFn: getTenantOverview });
