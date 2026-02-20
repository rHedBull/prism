// ---- Core Entity Types ----

export interface User {
  id: string;
  email: string;
  name: string;
  avatarUrl: string | null;
  role: UserRole;
  createdAt: string;
  updatedAt: string;
}

export type UserRole = "owner" | "admin" | "member" | "viewer";

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  description: string;
  ownerId: string;
  plan: PlanTier;
  memberCount: number;
  projectCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface Project {
  id: string;
  workspaceId: string;
  name: string;
  description: string;
  status: ProjectStatus;
  createdAt: string;
  updatedAt: string;
}

export type ProjectStatus = "active" | "archived" | "draft";

export interface Member {
  id: string;
  userId: string;
  workspaceId: string;
  role: UserRole;
  user: Pick<User, "id" | "email" | "name" | "avatarUrl">;
  joinedAt: string;
}

// ---- Billing ----

export type PlanTier = "free" | "starter" | "pro" | "enterprise";

export interface Subscription {
  id: string;
  workspaceId: string;
  plan: PlanTier;
  status: SubscriptionStatus;
  currentPeriodStart: string;
  currentPeriodEnd: string;
  cancelAtPeriodEnd: boolean;
  seats: number;
  monthlyPriceCents: number;
}

export type SubscriptionStatus = "active" | "past_due" | "canceled" | "trialing";

export interface Invoice {
  id: string;
  workspaceId: string;
  amountCents: number;
  currency: string;
  status: InvoiceStatus;
  pdfUrl: string | null;
  issuedAt: string;
  paidAt: string | null;
}

export type InvoiceStatus = "draft" | "open" | "paid" | "void" | "uncollectible";

export interface UsageMetrics {
  storage: { usedBytes: number; limitBytes: number };
  apiCalls: { used: number; limit: number };
  members: { used: number; limit: number };
}

// ---- Notifications ----

export interface Notification {
  id: string;
  userId: string;
  type: NotificationType;
  title: string;
  body: string;
  read: boolean;
  actionUrl: string | null;
  createdAt: string;
}

export type NotificationType =
  | "workspace_invite"
  | "member_joined"
  | "billing_alert"
  | "project_update"
  | "system";

export interface NotificationPreferences {
  email: Record<NotificationType, boolean>;
  inApp: Record<NotificationType, boolean>;
  push: Record<NotificationType, boolean>;
}

// ---- Analytics ----

export interface AnalyticsEvent {
  id: string;
  workspaceId: string;
  eventType: string;
  userId: string;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface DashboardData {
  totalWorkspaces: number;
  totalProjects: number;
  totalMembers: number;
  recentActivity: AnalyticsEvent[];
  usageMetrics: UsageMetrics;
}

export interface ActivityFeedItem {
  id: string;
  actorName: string;
  actorAvatarUrl: string | null;
  action: string;
  target: string;
  timestamp: string;
}

// ---- Files ----

export interface FileMetadata {
  id: string;
  workspaceId: string;
  name: string;
  mimeType: string;
  sizeBytes: number;
  uploadedBy: string;
  downloadUrl: string;
  createdAt: string;
}

// ---- Generic Response Types ----

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ApiError {
  status: number;
  message: string;
  code: string;
  details?: Record<string, string[]>;
}
