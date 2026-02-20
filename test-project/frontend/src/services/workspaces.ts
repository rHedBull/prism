import api from "./api";
import type { Workspace, Member, PaginatedResponse } from "../types/api";

interface CreateWorkspacePayload {
  name: string;
  description?: string;
}

interface UpdateWorkspacePayload {
  name?: string;
  description?: string;
}

interface InviteMemberPayload {
  email: string;
  role: "admin" | "member" | "viewer";
}

export async function fetchWorkspaces(
  page = 1,
  pageSize = 20,
): Promise<PaginatedResponse<Workspace>> {
  const { data } = await api.get<PaginatedResponse<Workspace>>("/workspaces", {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function fetchWorkspace(id: string): Promise<Workspace> {
  const { data } = await api.get<Workspace>(`/workspaces/${id}`);
  return data;
}

export async function createWorkspace(payload: CreateWorkspacePayload): Promise<Workspace> {
  const { data } = await api.post<Workspace>("/workspaces", payload);
  return data;
}

export async function updateWorkspace(
  id: string,
  payload: UpdateWorkspacePayload,
): Promise<Workspace> {
  const { data } = await api.patch<Workspace>(`/workspaces/${id}`, payload);
  return data;
}

export async function deleteWorkspace(id: string): Promise<void> {
  await api.delete(`/workspaces/${id}`);
}

export async function fetchMembers(
  workspaceId: string,
  page = 1,
  pageSize = 50,
): Promise<PaginatedResponse<Member>> {
  const { data } = await api.get<PaginatedResponse<Member>>(
    `/workspaces/${workspaceId}/members`,
    { params: { page, page_size: pageSize } },
  );
  return data;
}

export async function inviteMember(
  workspaceId: string,
  payload: InviteMemberPayload,
): Promise<Member> {
  const { data } = await api.post<Member>(
    `/workspaces/${workspaceId}/members`,
    payload,
  );
  return data;
}

export async function removeMember(workspaceId: string, memberId: string): Promise<void> {
  await api.delete(`/workspaces/${workspaceId}/members/${memberId}`);
}
