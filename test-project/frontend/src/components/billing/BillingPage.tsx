import React, { useState } from "react";
import { useSubscription, useUsage, useCancelSubscription } from "../../hooks/useBilling";
import { formatCurrency, formatFileSize, formatPercentage } from "../../utils/format";
import PlanSelector from "./PlanSelector";
import InvoiceTable from "./InvoiceTable";

export default function BillingPage() {
  // In a real app, workspace ID would come from context or route params
  const workspaceId = "current";
  const { data: subscription, isLoading: loadingSub } = useSubscription(workspaceId);
  const { data: usage, isLoading: loadingUsage } = useUsage(workspaceId);
  const cancelSub = useCancelSubscription(workspaceId);
  const [showPlanSelector, setShowPlanSelector] = useState(false);

  if (loadingSub) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Billing</h1>
        <p className="mt-1 text-sm text-gray-500">Manage your subscription and view usage</p>
      </div>

      {/* Current Plan */}
      {subscription && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Current Plan</h2>
              <p className="mt-1 text-3xl font-bold text-indigo-600">
                {subscription.plan.charAt(0).toUpperCase() + subscription.plan.slice(1)}
              </p>
              <p className="mt-1 text-sm text-gray-500">
                {formatCurrency(subscription.monthlyPriceCents)}/month
                {" · "}{subscription.seats} seats
              </p>
              {subscription.cancelAtPeriodEnd && (
                <p className="mt-2 text-sm text-amber-600">
                  Cancels at end of period ({subscription.currentPeriodEnd.slice(0, 10)})
                </p>
              )}
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setShowPlanSelector(true)}
                className="rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700"
              >
                Change Plan
              </button>
              {subscription.status === "active" && !subscription.cancelAtPeriodEnd && (
                <button
                  onClick={() => cancelSub.mutate()}
                  disabled={cancelSub.isPending}
                  className="rounded border border-red-300 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Usage */}
      {!loadingUsage && usage && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Usage</h2>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            <UsageBar
              label="Storage"
              used={usage.storage.usedBytes}
              limit={usage.storage.limitBytes}
              formatFn={formatFileSize}
            />
            <UsageBar
              label="API Calls"
              used={usage.apiCalls.used}
              limit={usage.apiCalls.limit}
              formatFn={(v) => v.toLocaleString()}
            />
            <UsageBar
              label="Members"
              used={usage.members.used}
              limit={usage.members.limit}
              formatFn={(v) => v.toString()}
            />
          </div>
        </div>
      )}

      {/* Plan Selector Modal */}
      {showPlanSelector && (
        <PlanSelector
          currentPlan={subscription?.plan ?? "free"}
          workspaceId={workspaceId}
          onClose={() => setShowPlanSelector(false)}
        />
      )}

      {/* Invoices */}
      <InvoiceTable workspaceId={workspaceId} />
    </div>
  );
}

function UsageBar({
  label,
  used,
  limit,
  formatFn,
}: {
  label: string;
  used: number;
  limit: number;
  formatFn: (v: number) => string;
}) {
  const percentage = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const isWarning = percentage >= 80;
  const isDanger = percentage >= 95;

  return (
    <div>
      <div className="flex justify-between text-sm">
        <span className="font-medium text-gray-700">{label}</span>
        <span className="text-gray-500">
          {formatFn(used)} / {formatFn(limit)} ({formatPercentage(used, limit)})
        </span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-100">
        <div
          className={`h-full rounded-full transition-all ${
            isDanger ? "bg-red-500" : isWarning ? "bg-amber-500" : "bg-indigo-500"
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
