import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getDashboard, queryEvents } from "../../services/analytics";
import { formatRelativeTime } from "../../utils/format";
import UsageChart from "../dashboard/UsageChart";

export default function AnalyticsPage() {
  const workspaceId = "current";
  const [eventType, setEventType] = useState<string>("");
  const [page, setPage] = useState(1);

  const { data: dashboard, isLoading: loadingDashboard } = useQuery({
    queryKey: ["analytics-dashboard", workspaceId],
    queryFn: () => getDashboard(workspaceId),
  });

  const { data: events, isLoading: loadingEvents } = useQuery({
    queryKey: ["analytics-events", workspaceId, eventType, page],
    queryFn: () =>
      queryEvents({
        workspaceId,
        eventType: eventType || undefined,
        page,
        pageSize: 20,
      }),
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
        <p className="mt-1 text-sm text-gray-500">Insights into your workspace activity</p>
      </div>

      {/* Summary cards */}
      {!loadingDashboard && dashboard && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <p className="text-sm font-medium text-gray-500">Total Workspaces</p>
            <p className="mt-1 text-3xl font-semibold text-gray-900">{dashboard.totalWorkspaces}</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <p className="text-sm font-medium text-gray-500">Total Projects</p>
            <p className="mt-1 text-3xl font-semibold text-gray-900">{dashboard.totalProjects}</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <p className="text-sm font-medium text-gray-500">Total Members</p>
            <p className="mt-1 text-3xl font-semibold text-gray-900">{dashboard.totalMembers}</p>
          </div>
        </div>
      )}

      <UsageChart workspaceId={workspaceId} period="month" />

      {/* Events table */}
      <div className="rounded-lg border border-gray-200 bg-white">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Events</h2>
          <select
            value={eventType}
            onChange={(e) => { setEventType(e.target.value); setPage(1); }}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm"
          >
            <option value="">All types</option>
            <option value="page_view">Page View</option>
            <option value="api_call">API Call</option>
            <option value="user_action">User Action</option>
          </select>
        </div>

        {loadingEvents ? (
          <div className="flex h-40 items-center justify-center">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          </div>
        ) : (
          <>
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">User</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {events?.items.map((event) => (
                  <tr key={event.id} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-6 py-3 text-sm font-medium text-gray-900">
                      {event.eventType}
                    </td>
                    <td className="whitespace-nowrap px-6 py-3 text-sm text-gray-500">
                      {event.userId}
                    </td>
                    <td className="whitespace-nowrap px-6 py-3 text-sm text-gray-400">
                      {formatRelativeTime(event.timestamp)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {events && events.totalPages > 1 && (
              <div className="flex items-center justify-between border-t border-gray-200 px-6 py-3">
                <p className="text-sm text-gray-500">
                  Page {events.page} of {events.totalPages}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="rounded border border-gray-300 px-3 py-1 text-sm disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page >= events.totalPages}
                    className="rounded border border-gray-300 px-3 py-1 text-sm disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
