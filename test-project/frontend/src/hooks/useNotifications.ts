import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as notificationsService from "../services/notifications";

const NOTIFICATIONS_KEY = ["notifications"] as const;

export function useNotifications(page = 1, pageSize = 20, unreadOnly = false) {
  return useQuery({
    queryKey: [...NOTIFICATIONS_KEY, { page, pageSize, unreadOnly }],
    queryFn: () => notificationsService.getNotifications(page, pageSize, unreadOnly),
    refetchInterval: 30_000, // Poll every 30s
  });
}

export function useUnreadCount() {
  const { data } = useNotifications(1, 1, true);
  return data?.total ?? 0;
}

export function useMarkAsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: notificationsService.markAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
    },
  });
}

export function useMarkAllAsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: notificationsService.markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
    },
  });
}

export function useNotificationPreferences() {
  return useQuery({
    queryKey: [...NOTIFICATIONS_KEY, "preferences"],
    queryFn: notificationsService.getPreferences,
  });
}

export function useUpdateNotificationPreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: notificationsService.updatePreferences,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [...NOTIFICATIONS_KEY, "preferences"],
      });
    },
  });
}
