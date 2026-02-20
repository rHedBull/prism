import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as workspacesService from "../services/workspaces";

const WORKSPACES_KEY = ["workspaces"] as const;

export function useWorkspaces(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: [...WORKSPACES_KEY, { page, pageSize }],
    queryFn: () => workspacesService.fetchWorkspaces(page, pageSize),
  });
}

export function useWorkspace(id: string) {
  return useQuery({
    queryKey: [...WORKSPACES_KEY, id],
    queryFn: () => workspacesService.fetchWorkspace(id),
    enabled: !!id,
  });
}

export function useCreateWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: workspacesService.createWorkspace,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WORKSPACES_KEY });
    },
  });
}

export function useUpdateWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string; name?: string; description?: string }) =>
      workspacesService.updateWorkspace(id, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: [...WORKSPACES_KEY, variables.id] });
      queryClient.invalidateQueries({ queryKey: WORKSPACES_KEY });
    },
  });
}

export function useDeleteWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: workspacesService.deleteWorkspace,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WORKSPACES_KEY });
    },
  });
}

export function useMembers(workspaceId: string, page = 1) {
  return useQuery({
    queryKey: [...WORKSPACES_KEY, workspaceId, "members", { page }],
    queryFn: () => workspacesService.fetchMembers(workspaceId, page),
    enabled: !!workspaceId,
  });
}

export function useInviteMember(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { email: string; role: "admin" | "member" | "viewer" }) =>
      workspacesService.inviteMember(workspaceId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [...WORKSPACES_KEY, workspaceId, "members"],
      });
    },
  });
}

export function useRemoveMember(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (memberId: string) =>
      workspacesService.removeMember(workspaceId, memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [...WORKSPACES_KEY, workspaceId, "members"],
      });
    },
  });
}
