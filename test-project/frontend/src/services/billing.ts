import api from "./api";
import type { Subscription, Invoice, PaginatedResponse, PlanTier, UsageMetrics } from "../types/api";

export async function getSubscription(workspaceId: string): Promise<Subscription> {
  const { data } = await api.get<Subscription>(`/billing/workspaces/${workspaceId}/subscription`);
  return data;
}

export async function updatePlan(
  workspaceId: string,
  plan: PlanTier,
): Promise<Subscription> {
  const { data } = await api.post<Subscription>(
    `/billing/workspaces/${workspaceId}/subscription/change`,
    { plan },
  );
  return data;
}

export async function cancelSubscription(workspaceId: string): Promise<Subscription> {
  const { data } = await api.post<Subscription>(
    `/billing/workspaces/${workspaceId}/subscription/cancel`,
  );
  return data;
}

export async function getInvoices(
  workspaceId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedResponse<Invoice>> {
  const { data } = await api.get<PaginatedResponse<Invoice>>(
    `/billing/workspaces/${workspaceId}/invoices`,
    { params: { page, page_size: pageSize } },
  );
  return data;
}

export async function getUsage(workspaceId: string): Promise<UsageMetrics> {
  const { data } = await api.get<UsageMetrics>(
    `/billing/workspaces/${workspaceId}/usage`,
  );
  return data;
}
