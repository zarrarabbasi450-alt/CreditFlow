import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createSchedule, getSchedules } from "@/lib/api/scheduler";
export const useScheduler = () => useQuery({ queryKey: ["scheduler"], queryFn: getSchedules });
export function useCreateSchedule() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createSchedule,
    onSuccess: () => client.invalidateQueries({ queryKey: ["scheduler"] }),
  });
}
