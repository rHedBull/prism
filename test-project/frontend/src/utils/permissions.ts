import type { UserRole, Member } from "../types/api";

const ROLE_HIERARCHY: Record<UserRole, number> = {
  owner: 4,
  admin: 3,
  member: 2,
  viewer: 1,
};

export function hasPermission(
  userRole: UserRole,
  requiredRole: UserRole,
): boolean {
  return ROLE_HIERARCHY[userRole] >= ROLE_HIERARCHY[requiredRole];
}

export function canManageMembers(userRole: UserRole): boolean {
  return hasPermission(userRole, "admin");
}

export function canAccessBilling(userRole: UserRole): boolean {
  return hasPermission(userRole, "owner");
}

export function canEditWorkspace(userRole: UserRole): boolean {
  return hasPermission(userRole, "admin");
}

export function canCreateProject(userRole: UserRole): boolean {
  return hasPermission(userRole, "member");
}

export function canDeleteProject(userRole: UserRole): boolean {
  return hasPermission(userRole, "admin");
}

export function canRemoveMember(
  actorRole: UserRole,
  targetMember: Member,
): boolean {
  if (targetMember.role === "owner") return false;
  return ROLE_HIERARCHY[actorRole] > ROLE_HIERARCHY[targetMember.role];
}

export function canChangeRole(
  actorRole: UserRole,
  targetRole: UserRole,
  newRole: UserRole,
): boolean {
  if (targetRole === "owner") return false;
  // Can only assign roles below your own level
  return (
    ROLE_HIERARCHY[actorRole] > ROLE_HIERARCHY[targetRole] &&
    ROLE_HIERARCHY[actorRole] > ROLE_HIERARCHY[newRole]
  );
}

export function getAssignableRoles(actorRole: UserRole): UserRole[] {
  const level = ROLE_HIERARCHY[actorRole];
  return (Object.entries(ROLE_HIERARCHY) as [UserRole, number][])
    .filter(([role, roleLevel]) => roleLevel < level && role !== "owner")
    .map(([role]) => role);
}
