import { useQuery } from "@tanstack/react-query";
import { getNotifications } from "@/lib/api/notifications";
export const useNotifications = () => useQuery({ queryKey: ["notifications"], queryFn: getNotifications });
