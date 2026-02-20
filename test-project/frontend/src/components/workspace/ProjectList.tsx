import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../services/api";
import type { Project, PaginatedResponse } from "../../types/api";
import { formatDate } from "../../utils/format";

interface ProjectListProps {
  workspaceId: string;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  archived: "bg-gray-100 text-gray-600",
  draft: "bg-yellow-100 text-yellow-700",
};

export default function ProjectList({ workspaceId }: ProjectListProps) {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectDesc, setNewProjectDesc] = useState("");
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["projects", workspaceId],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<Project>>(
        `/workspaces/${workspaceId}/projects`,
      );
      return data;
    },
  });

  const createProject = useMutation({
    mutationFn: async (payload: { name: string; description: string }) => {
      const { data } = await api.post<Project>(
        `/workspaces/${workspaceId}/projects`,
        payload,
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", workspaceId] });
      setShowCreateForm(false);
      setNewProjectName("");
      setNewProjectDesc("");
    },
  });

  const archiveProject = useMutation({
    mutationFn: async (projectId: string) => {
      await api.patch(`/workspaces/${workspaceId}/projects/${projectId}`, {
        status: "archived",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", workspaceId] });
    },
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-36 animate-pulse rounded-lg border border-gray-200 bg-gray-50" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">{data?.total ?? 0} projects</p>
        <button
          onClick={() => setShowCreateForm(true)}
          className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700"
        >
          New Project
        </button>
      </div>

      {showCreateForm && (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4">
          <div className="space-y-3">
            <input
              type="text"
              placeholder="Project name"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              className="block w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <textarea
              placeholder="Description (optional)"
              value={newProjectDesc}
              onChange={(e) => setNewProjectDesc(e.target.value)}
              rows={2}
              className="block w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <div className="flex gap-2">
              <button
                onClick={() =>
                  createProject.mutate({
                    name: newProjectName,
                    description: newProjectDesc,
                  })
                }
                disabled={!newProjectName.trim() || createProject.isPending}
                className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                Create
              </button>
              <button
                onClick={() => setShowCreateForm(false)}
                className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.items.map((project) => (
          <div
            key={project.id}
            className="rounded-lg border border-gray-200 bg-white p-5 transition-shadow hover:shadow-md"
          >
            <div className="flex items-start justify-between">
              <h3 className="font-medium text-gray-900">{project.name}</h3>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  STATUS_COLORS[project.status] ?? "bg-gray-100 text-gray-600"
                }`}
              >
                {project.status}
              </span>
            </div>
            {project.description && (
              <p className="mt-2 text-sm text-gray-500 line-clamp-2">
                {project.description}
              </p>
            )}
            <div className="mt-4 flex items-center justify-between">
              <span className="text-xs text-gray-400">
                Created {formatDate(project.createdAt)}
              </span>
              {project.status === "active" && (
                <button
                  onClick={() => archiveProject.mutate(project.id)}
                  className="text-xs text-gray-400 hover:text-red-500"
                >
                  Archive
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
