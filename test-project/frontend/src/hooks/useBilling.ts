import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { PlanTier } from "../types/api";
import * as billingService from "../services/billing";

const BILLING_KEY = ["billing"] as const;

export function useSubscription(workspaceId: string) {
  return useQuery({
    queryKey: [...BILLING_KEY, workspaceId, "subscription"],
    queryFn: () => billingService.getSubscription(workspaceId),
    enabled: !!workspaceId,
  });
}

export function useUpdatePlan(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (plan: PlanTier) => billingService.updatePlan(workspaceId, plan),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [...BILLING_KEY, workspaceId, "subscription"],
      });
    },
  });
}

export function useCancelSubscription(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => billingService.cancelSubscription(workspaceId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [...BILLING_KEY, workspaceId, "subscription"],
      });
    },
  });
}

export function useInvoices(workspaceId: string, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: [...BILLING_KEY, workspaceId, "invoices", { page, pageSize }],
    queryFn: () => billingService.getInvoices(workspaceId, page, pageSize),
    enabled: !!workspaceId,
  });
}

export function useUsage(workspaceId: string) {
  return useQuery({
    queryKey: [...BILLING_KEY, workspaceId, "usage"],
    queryFn: () => billingService.getUsage(workspaceId),
    enabled: !!workspaceId,
    refetchInterval: 60_000, // Refresh usage every minute
  });
}
