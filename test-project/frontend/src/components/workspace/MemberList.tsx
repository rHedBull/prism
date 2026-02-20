import React, { useState } from "react";
import { useMembers, useInviteMember, useRemoveMember } from "../../hooks/useWorkspaces";
import { useAuth } from "../../hooks/useAuth";
import { canManageMembers, canRemoveMember, getAssignableRoles } from "../../utils/permissions";
import type { UserRole } from "../../types/api";
import { formatDate } from "../../utils/format";

interface MemberListProps {
  workspaceId: string;
}

export default function MemberList({ workspaceId }: MemberListProps) {
  const { user } = useAuth();
  const { data: membersData, isLoading } = useMembers(workspaceId);
  const inviteMember = useInviteMember(workspaceId);
  const removeMember = useRemoveMember(workspaceId);

  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "member" | "viewer">("member");

  // Determine current user's role in this workspace
  const currentMember = membersData?.items.find((m) => m.userId === user?.id);
  const currentRole: UserRole = currentMember?.role ?? "viewer";
  const canManage = canManageMembers(currentRole);
  const assignableRoles = getAssignableRoles(currentRole) as ("admin" | "member" | "viewer")[];

  const handleInvite = () => {
    if (!inviteEmail.trim()) return;
    inviteMember.mutate(
      { email: inviteEmail, role: inviteRole },
      {
        onSuccess: () => {
          setInviteEmail("");
          setShowInviteForm(false);
        },
      },
    );
  };

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-14 animate-pulse rounded bg-gray-100" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">{membersData?.total ?? 0} members</p>
        {canManage && (
          <button
            onClick={() => setShowInviteForm(!showInviteForm)}
            className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700"
          >
            Invite Member
          </button>
        )}
      </div>

      {showInviteForm && (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4">
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700">Email</label>
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colleague@company.com"
                className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Role</label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as typeof inviteRole)}
                className="mt-1 block rounded border border-gray-300 px-3 py-2 text-sm"
              >
                {assignableRoles.map((role) => (
                  <option key={role} value={role}>
                    {role.charAt(0).toUpperCase() + role.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={handleInvite}
              disabled={inviteMember.isPending || !inviteEmail.trim()}
              className="rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {inviteMember.isPending ? "Sending..." : "Send Invite"}
            </button>
          </div>
          {inviteMember.isError && (
            <p className="mt-2 text-sm text-red-600">Failed to send invite. Please try again.</p>
          )}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Member
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Role
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Joined
              </th>
              {canManage && (
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {membersData?.items.map((member) => (
              <tr key={member.id}>
                <td className="whitespace-nowrap px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-xs font-medium text-indigo-700">
                      {member.user.name
                        .split(" ")
                        .map((n) => n[0])
                        .join("")
                        .toUpperCase()
                        .slice(0, 2)}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">{member.user.name}</p>
                      <p className="text-xs text-gray-500">{member.user.email}</p>
                    </div>
                  </div>
                </td>
                <td className="whitespace-nowrap px-6 py-4">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      member.role === "owner"
                        ? "bg-purple-100 text-purple-700"
                        : member.role === "admin"
                          ? "bg-blue-100 text-blue-700"
                          : "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {member.role}
                  </span>
                </td>
                <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                  {formatDate(member.joinedAt)}
                </td>
                {canManage && (
                  <td className="whitespace-nowrap px-6 py-4 text-right">
                    {canRemoveMember(currentRole, member) && (
                      <button
                        onClick={() => removeMember.mutate(member.id)}
                        className="text-sm text-red-500 hover:text-red-700"
                      >
                        Remove
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
