import React, { useState } from "react";
import { useParams } from "react-router-dom";
import { useWorkspace } from "../../hooks/useWorkspaces";
import ProjectList from "./ProjectList";
import MemberList from "./MemberList";

type Tab = "projects" | "members" | "settings";

export default function WorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const { data: workspace, isLoading, error } = useWorkspace(id!);
  const [activeTab, setActiveTab] = useState<Tab>("projects");

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
      </div>
    );
  }

  if (error || !workspace) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
        <p className="text-red-700">Failed to load workspace</p>
      </div>
    );
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "projects", label: "Projects" },
    { key: "members", label: `Members (${workspace.memberCount})` },
    { key: "settings", label: "Settings" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{workspace.name}</h1>
        {workspace.description && (
          <p className="mt-1 text-sm text-gray-500">{workspace.description}</p>
        )}
      </div>

      {/* Tab bar */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`border-b-2 pb-3 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "projects" && <ProjectList workspaceId={workspace.id} />}
      {activeTab === "members" && <MemberList workspaceId={workspace.id} />}
      {activeTab === "settings" && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="text-lg font-medium text-gray-900">Workspace Settings</h3>
          <div className="mt-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Name</label>
              <input
                type="text"
                defaultValue={workspace.name}
                className="mt-1 block w-full rounded border border-gray-300 px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Description</label>
              <textarea
                defaultValue={workspace.description}
                rows={3}
                className="mt-1 block w-full rounded border border-gray-300 px-3 py-2"
              />
            </div>
            <button className="rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700">
              Save Changes
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
