import React, { useState } from "react";
import { useAuth } from "../../hooks/useAuth";
import { updateProfile } from "../../services/auth";
import NotificationSettings from "./NotificationSettings";

type SettingsTab = "profile" | "notifications" | "api-keys";

export default function SettingsPage() {
  const { user, loadProfile } = useAuth();
  const [activeTab, setActiveTab] = useState<SettingsTab>("profile");
  const [name, setName] = useState(user?.name ?? "");
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const tabs: { key: SettingsTab; label: string }[] = [
    { key: "profile", label: "Profile" },
    { key: "notifications", label: "Notifications" },
    { key: "api-keys", label: "API Keys" },
  ];

  const handleSaveProfile = async () => {
    setSaving(true);
    setSaveSuccess(false);
    try {
      await updateProfile({ name });
      await loadProfile();
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">Manage your account settings</p>
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

      {activeTab === "profile" && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="text-lg font-medium text-gray-900">Profile Information</h3>
          <div className="mt-4 max-w-md space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Email</label>
              <input
                type="email"
                value={user?.email ?? ""}
                disabled
                className="mt-1 block w-full rounded border border-gray-200 bg-gray-50 px-3 py-2 text-gray-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Full name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleSaveProfile}
                disabled={saving}
                className="rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save Changes"}
              </button>
              {saveSuccess && (
                <span className="text-sm text-green-600">Saved successfully</span>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === "notifications" && <NotificationSettings />}

      {activeTab === "api-keys" && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="text-lg font-medium text-gray-900">API Keys</h3>
          <p className="mt-1 text-sm text-gray-500">
            Manage API keys for programmatic access to your workspaces
          </p>
          <div className="mt-4">
            <button className="rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700">
              Generate New Key
            </button>
          </div>
          <div className="mt-4 rounded border border-gray-200 p-4 text-center text-sm text-gray-400">
            No API keys created yet
          </div>
        </div>
      )}
    </div>
  );
}
