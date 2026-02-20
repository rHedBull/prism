import api from "./api";
import type { DashboardData, AnalyticsEvent, PaginatedResponse, ActivityFeedItem } from "../types/api";

interface EventQueryParams {
  workspaceId: string;
  eventType?: string;
  startDate?: string;
  endDate?: string;
  page?: number;
  pageSize?: number;
}

interface UsageMetricsParams {
  workspaceId: string;
  period: "day" | "week" | "month";
  startDate?: string;
  endDate?: string;
}

export interface UsageDataPoint {
  date: string;
  apiCalls: number;
  storageBytes: number;
  activeUsers: number;
}

export async function getDashboard(workspaceId: string): Promise<DashboardData> {
  const { data } = await api.get<DashboardData>(
    `/analytics/workspaces/${workspaceId}/dashboard`,
  );
  return data;
}

export async function queryEvents(
  params: EventQueryParams,
): Promise<PaginatedResponse<AnalyticsEvent>> {
  const { workspaceId, ...rest } = params;
  const { data } = await api.get<PaginatedResponse<AnalyticsEvent>>(
    `/analytics/workspaces/${workspaceId}/events`,
    { params: rest },
  );
  return data;
}

export async function getUsageMetrics(
  params: UsageMetricsParams,
): Promise<UsageDataPoint[]> {
  const { workspaceId, ...rest } = params;
  const { data } = await api.get<UsageDataPoint[]>(
    `/analytics/workspaces/${workspaceId}/usage-metrics`,
    { params: rest },
  );
  return data;
}

export async function getActivityFeed(
  workspaceId: string,
  limit = 20,
): Promise<ActivityFeedItem[]> {
  const { data } = await api.get<ActivityFeedItem[]>(
    `/analytics/workspaces/${workspaceId}/activity`,
    { params: { limit } },
  );
  return data;
}
