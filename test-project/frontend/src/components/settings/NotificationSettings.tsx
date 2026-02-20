import React from "react";
import {
  useNotificationPreferences,
  useUpdateNotificationPreferences,
} from "../../hooks/useNotifications";
import type { NotificationType, NotificationPreferences } from "../../types/api";

const EVENT_TYPES: { type: NotificationType; label: string }[] = [
  { type: "workspace_invite", label: "Workspace invitations" },
  { type: "member_joined", label: "New member joined" },
  { type: "billing_alert", label: "Billing alerts" },
  { type: "project_update", label: "Project updates" },
  { type: "system", label: "System notifications" },
];

const CHANNELS: { key: keyof NotificationPreferences; label: string }[] = [
  { key: "email", label: "Email" },
  { key: "inApp", label: "In-App" },
  { key: "push", label: "Push" },
];

export default function NotificationSettings() {
  const { data: preferences, isLoading } = useNotificationPreferences();
  const updatePrefs = useUpdateNotificationPreferences();

  const handleToggle = (
    channel: keyof NotificationPreferences,
    eventType: NotificationType,
  ) => {
    if (!preferences) return;

    const updatedChannel = {
      ...preferences[channel],
      [eventType]: !preferences[channel][eventType],
    };

    updatePrefs.mutate({
      [channel]: updatedChannel,
    });
  };

  if (isLoading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
      </div>
    );
  }

  if (!preferences) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6 text-center text-gray-400">
        Failed to load notification preferences
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h3 className="text-lg font-medium text-gray-900">Notification Preferences</h3>
      <p className="mt-1 text-sm text-gray-500">
        Choose how you want to be notified for each event type
      </p>

      <div className="mt-6 overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="pb-3 pr-8 text-left text-sm font-medium text-gray-700">
                Event
              </th>
              {CHANNELS.map((channel) => (
                <th
                  key={channel.key}
                  className="pb-3 text-center text-sm font-medium text-gray-700"
                  style={{ minWidth: 80 }}
                >
                  {channel.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {EVENT_TYPES.map((event) => (
              <tr key={event.type}>
                <td className="py-4 pr-8 text-sm text-gray-900">{event.label}</td>
                {CHANNELS.map((channel) => {
                  const enabled = preferences[channel.key]?.[event.type] ?? false;
                  return (
                    <td key={channel.key} className="py-4 text-center">
                      <button
                        onClick={() => handleToggle(channel.key, event.type)}
                        disabled={updatePrefs.isPending}
                        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
                          enabled ? "bg-indigo-600" : "bg-gray-200"
                        }`}
                        role="switch"
                        aria-checked={enabled}
                      >
                        <span
                          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-transform ${
                            enabled ? "translate-x-5" : "translate-x-0"
                          }`}
                        />
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
