import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cancelSchedule, createSchedule, getSchedulerSummary, getSchedules, updateSchedule } from "@/lib/api/scheduler";
import type { CreateScheduleRequest, UpdateScheduleRequest } from "@/types";

export const useScheduler = (params?: { start?: string; end?: string; timezone?: string }) =>
  useQuery({ queryKey: ["scheduler", params], queryFn: () => getSchedules(params) });

export const useSchedulerSummary = () =>
  useQuery({ queryKey: ["scheduler-summary"], queryFn: getSchedulerSummary });

export function useCreateSchedule() {
  const client = useQueryClient();
  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["scheduler"] }),
      client.invalidateQueries({ queryKey: ["scheduler-summary"] }),
      client.invalidateQueries({ queryKey: ["product-view", "scheduler"] }),
    ]);
  };
  return useMutation({
    mutationFn: (payload: CreateScheduleRequest) => createSchedule(payload),
    onSuccess: refresh,
  });
}

export function useSchedulerMutations() {
  const client = useQueryClient();
  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["scheduler"] }),
      client.invalidateQueries({ queryKey: ["scheduler-summary"] }),
      client.invalidateQueries({ queryKey: ["product-view", "scheduler"] }),
    ]);
  };
  return {
    create: useMutation({ mutationFn: (payload: CreateScheduleRequest) => createSchedule(payload), onSuccess: refresh }),
    update: useMutation({
      mutationFn: ({ id, payload }: { id: string; payload: UpdateScheduleRequest }) => updateSchedule(id, payload),
      onSuccess: refresh,
    }),
    cancel: useMutation({ mutationFn: (id: string) => cancelSchedule(id), onSuccess: refresh }),
  };
}
