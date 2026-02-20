import React from "react";
import { Link } from "react-router-dom";
import { useWorkspaces } from "../../hooks/useWorkspaces";
import { useNotifications } from "../../hooks/useNotifications";
import { formatRelativeTime } from "../../utils/format";
import ActivityFeed from "./ActivityFeed";
import UsageChart from "./UsageChart";

export default function DashboardPage() {
  const { data: workspacesData, isLoading: loadingWorkspaces } = useWorkspaces();
  const { data: notificationsData } = useNotifications(1, 5);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Overview of your workspaces and recent activity
        </p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <p className="text-sm font-medium text-gray-500">Workspaces</p>
          <p className="mt-1 text-3xl font-semibold text-gray-900">
            {workspacesData?.total ?? 0}
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <p className="text-sm font-medium text-gray-500">Projects</p>
          <p className="mt-1 text-3xl font-semibold text-gray-900">
            {workspacesData?.items.reduce((sum, ws) => sum + ws.projectCount, 0) ?? 0}
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <p className="text-sm font-medium text-gray-500">Unread Notifications</p>
          <p className="mt-1 text-3xl font-semibold text-gray-900">
            {notificationsData?.total ?? 0}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Workspace list */}
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Your Workspaces</h2>
          {loadingWorkspaces ? (
            <div className="py-8 text-center text-gray-400">Loading...</div>
          ) : workspacesData?.items.length === 0 ? (
            <div className="py-8 text-center text-gray-400">
              No workspaces yet. Create one to get started.
            </div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {workspacesData?.items.map((ws) => (
                <li key={ws.id}>
                  <Link
                    to={`/workspaces/${ws.id}`}
                    className="flex items-center justify-between py-3 hover:bg-gray-50"
                  >
                    <div>
                      <p className="font-medium text-gray-900">{ws.name}</p>
                      <p className="text-sm text-gray-500">
                        {ws.memberCount} members · {ws.projectCount} projects
                      </p>
                    </div>
                    <span className="rounded-full bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700">
                      {ws.plan}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Activity Feed */}
        <ActivityFeed />
      </div>

      {/* Usage Chart */}
      <UsageChart />

      {/* Recent notifications */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Recent Notifications</h2>
        {notificationsData?.items.length === 0 ? (
          <p className="text-sm text-gray-400">No notifications</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {notificationsData?.items.map((n) => (
              <li key={n.id} className="flex items-start gap-3 py-3">
                <div
                  className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                    n.read ? "bg-gray-300" : "bg-indigo-500"
                  }`}
                />
                <div>
                  <p className="text-sm font-medium text-gray-900">{n.title}</p>
                  <p className="text-sm text-gray-500">{n.body}</p>
                  <p className="mt-1 text-xs text-gray-400">
                    {formatRelativeTime(n.createdAt)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
