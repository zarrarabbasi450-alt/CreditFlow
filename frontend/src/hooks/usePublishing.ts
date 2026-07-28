import { useMutation, useQuery } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";
import {
  connectLinkedIn,
  connectLinkedInDev,
  disconnectLinkedIn,
  getPublishing,
  publishContentToLinkedIn,
  publishToLinkedIn,
  refreshLinkedInTokens,
} from "@/lib/api/publishing";
import type { DevLinkedInConnectionRequest, PublishContentRequest, PublishRequest } from "@/types";
export const usePublishing = () => useQuery({ queryKey: ["publishing"], queryFn: getPublishing });

export function usePublishingMutations() {
  const queryClient = useQueryClient();
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["publishing"] }),
      queryClient.invalidateQueries({ queryKey: ["product-view", "publishing"] }),
    ]);
  };
  return {
    connect: useMutation({ mutationFn: connectLinkedIn, onSuccess: refresh }),
    devConnect: useMutation({
      mutationFn: (payload: DevLinkedInConnectionRequest) => connectLinkedInDev(payload),
      onSuccess: refresh,
    }),
    disconnect: useMutation({ mutationFn: (connectionId: string) => disconnectLinkedIn(connectionId), onSuccess: refresh }),
    publishManual: useMutation({ mutationFn: (payload: PublishRequest) => publishToLinkedIn(payload), onSuccess: refresh }),
    publishContent: useMutation({
      mutationFn: (payload: PublishContentRequest) => publishContentToLinkedIn(payload),
      onSuccess: refresh,
    }),
    refreshTokens: useMutation({ mutationFn: refreshLinkedInTokens, onSuccess: refresh }),
  };
}

export const usePublishToLinkedIn = () =>
  useMutation({
    mutationFn: async (data: Pick<PublishRequest, "caption" | "imageUrl">) => {
      const publishing = await getPublishing();
      const connection = publishing.connections[0];
      if (!connection) throw new Error("No LinkedIn connection is available");
      return publishToLinkedIn({
        ...data,
        connectionId: connection.id,
      });
    },
  });
