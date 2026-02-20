import React from "react";
import { useQuery } from "@tanstack/react-query";
import { getActivityFeed } from "../../services/analytics";
import { formatRelativeTime } from "../../utils/format";
import type { ActivityFeedItem } from "../../types/api";

interface ActivityFeedProps {
  workspaceId?: string;
  limit?: number;
}

export default function ActivityFeed({ workspaceId, limit = 15 }: ActivityFeedProps) {
  const { data: activities, isLoading } = useQuery({
    queryKey: ["activity-feed", workspaceId, limit],
    queryFn: () => getActivityFeed(workspaceId ?? "all", limit),
    refetchInterval: 30_000,
    enabled: true,
  });

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h2 className="mb-4 text-lg font-semibold text-gray-900">Recent Activity</h2>
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="h-8 w-8 animate-pulse rounded-full bg-gray-200" />
              <div className="flex-1 space-y-1">
                <div className="h-3 w-3/4 animate-pulse rounded bg-gray-200" />
                <div className="h-2 w-1/2 animate-pulse rounded bg-gray-200" />
              </div>
            </div>
          ))}
        </div>
      ) : activities?.length === 0 ? (
        <p className="py-4 text-center text-sm text-gray-400">No recent activity</p>
      ) : (
        <ul className="space-y-3">
          {activities?.map((item: ActivityFeedItem) => (
            <li key={item.id} className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-medium text-indigo-700">
                {item.actorName
                  .split(" ")
                  .map((n) => n[0])
                  .join("")
                  .toUpperCase()
                  .slice(0, 2)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-gray-900">
                  <span className="font-medium">{item.actorName}</span>{" "}
                  {item.action}{" "}
                  <span className="font-medium">{item.target}</span>
                </p>
                <p className="text-xs text-gray-400">
                  {formatRelativeTime(item.timestamp)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
