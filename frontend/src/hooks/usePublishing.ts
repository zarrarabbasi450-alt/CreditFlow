import { useMutation, useQuery } from "@tanstack/react-query";
import { getPublishing, publishToLinkedIn } from "@/lib/api/publishing";
import type { PublishRequest } from "@/types";
export const usePublishing = () => useQuery({ queryKey: ["publishing"], queryFn: getPublishing });
export const usePublishToLinkedIn = () =>
  useMutation({
    mutationFn: async (data: Pick<PublishRequest, "caption" | "image">) => {
      const publishing = await getPublishing();
      const connection = publishing.connections[0];
      if (!connection) throw new Error("No LinkedIn connection is available");
      return publishToLinkedIn({
        ...data,
        accountId: connection.accountId,
        connectionId: connection.id,
      });
    },
  });
