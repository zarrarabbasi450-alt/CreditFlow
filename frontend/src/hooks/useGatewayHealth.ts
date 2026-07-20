import { useQuery } from "@tanstack/react-query";
import { getGatewayStatus } from "@/lib/api/gateway";
export const useGatewayHealth = () =>
  useQuery({ queryKey: ["gateway-status"], queryFn: getGatewayStatus, staleTime: 30_000 });
