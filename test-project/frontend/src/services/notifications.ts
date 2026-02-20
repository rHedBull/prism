import api from "./api";
import type { Notification, NotificationPreferences, PaginatedResponse } from "../types/api";

export async function getNotifications(
  page = 1,
  pageSize = 20,
  unreadOnly = false,
): Promise<PaginatedResponse<Notification>> {
  const { data } = await api.get<PaginatedResponse<Notification>>("/notifications", {
    params: { page, page_size: pageSize, unread_only: unreadOnly || undefined },
  });
  return data;
}

export async function markAsRead(notificationIds: string[]): Promise<void> {
  await api.post("/notifications/mark-read", { ids: notificationIds });
}

export async function markAllAsRead(): Promise<void> {
  await api.post("/notifications/mark-all-read");
}

export async function getPreferences(): Promise<NotificationPreferences> {
  const { data } = await api.get<NotificationPreferences>("/notifications/preferences");
  return data;
}

export async function updatePreferences(
  prefs: Partial<NotificationPreferences>,
): Promise<NotificationPreferences> {
  const { data } = await api.patch<NotificationPreferences>(
    "/notifications/preferences",
    prefs,
  );
  return data;
}
