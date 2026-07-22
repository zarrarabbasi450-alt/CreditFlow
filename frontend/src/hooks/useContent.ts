import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  approveContent,
  createContent,
  deleteContent,
  getContent,
  publishContent,
  updateContent,
  uploadContentImage,
  type ContentPayload,
} from "@/lib/api/content";
export const useContent = () => useQuery({ queryKey: ["content"], queryFn: getContent });

export function useContentMutations() {
  const queryClient = useQueryClient();
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["content"] }),
      queryClient.invalidateQueries({ queryKey: ["product-view", "content"] }),
    ]);
  };
  return {
    create: useMutation({ mutationFn: (payload: ContentPayload) => createContent(payload), onSuccess: refresh }),
    update: useMutation({
      mutationFn: ({ id, payload }: { id: string; payload: Partial<ContentPayload> }) => updateContent(id, payload),
      onSuccess: refresh,
    }),
    remove: useMutation({ mutationFn: (id: string) => deleteContent(id), onSuccess: refresh }),
    approve: useMutation({ mutationFn: (id: string) => approveContent(id), onSuccess: refresh }),
    publish: useMutation({ mutationFn: (id: string) => publishContent(id), onSuccess: refresh }),
    uploadImage: useMutation({
      mutationFn: ({ id, file }: { id: string; file: File }) => uploadContentImage(id, file),
      onSuccess: refresh,
    }),
  };
}
