import React from "react";
import { useUpdatePlan } from "../../hooks/useBilling";
import type { PlanTier } from "../../types/api";
import { formatCurrency } from "../../utils/format";

interface PlanSelectorProps {
  currentPlan: PlanTier;
  workspaceId: string;
  onClose: () => void;
}

interface PlanInfo {
  tier: PlanTier;
  name: string;
  priceCents: number;
  features: string[];
  seats: number;
  highlighted?: boolean;
}

const PLANS: PlanInfo[] = [
  {
    tier: "free",
    name: "Free",
    priceCents: 0,
    seats: 3,
    features: ["3 members", "1 GB storage", "1,000 API calls/month", "Community support"],
  },
  {
    tier: "starter",
    name: "Starter",
    priceCents: 2900,
    seats: 10,
    features: ["10 members", "10 GB storage", "10,000 API calls/month", "Email support"],
  },
  {
    tier: "pro",
    name: "Pro",
    priceCents: 7900,
    seats: 50,
    highlighted: true,
    features: [
      "50 members",
      "100 GB storage",
      "100,000 API calls/month",
      "Priority support",
      "Advanced analytics",
      "Custom integrations",
    ],
  },
  {
    tier: "enterprise",
    name: "Enterprise",
    priceCents: 29900,
    seats: -1, // unlimited
    features: [
      "Unlimited members",
      "Unlimited storage",
      "Unlimited API calls",
      "Dedicated support",
      "SSO / SAML",
      "SLA guarantee",
      "Custom contracts",
    ],
  },
];

export default function PlanSelector({ currentPlan, workspaceId, onClose }: PlanSelectorProps) {
  const updatePlan = useUpdatePlan(workspaceId);

  const handleSelect = async (tier: PlanTier) => {
    if (tier === currentPlan) return;
    try {
      await updatePlan.mutateAsync(tier);
      onClose();
    } catch {
      // Error handled by React Query
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-xl bg-white p-8">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-900">Choose a Plan</h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {PLANS.map((plan) => {
            const isCurrent = plan.tier === currentPlan;
            return (
              <div
                key={plan.tier}
                className={`relative rounded-lg border-2 p-6 ${
                  plan.highlighted
                    ? "border-indigo-600 shadow-lg"
                    : isCurrent
                      ? "border-indigo-300 bg-indigo-50"
                      : "border-gray-200"
                }`}
              >
                {plan.highlighted && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-indigo-600 px-3 py-0.5 text-xs font-medium text-white">
                    Most Popular
                  </span>
                )}
                <h3 className="text-lg font-semibold text-gray-900">{plan.name}</h3>
                <p className="mt-2 text-3xl font-bold text-gray-900">
                  {plan.priceCents === 0
                    ? "Free"
                    : formatCurrency(plan.priceCents)}
                  {plan.priceCents > 0 && (
                    <span className="text-sm font-normal text-gray-500">/mo</span>
                  )}
                </p>
                <ul className="mt-4 space-y-2">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2 text-sm text-gray-600">
                      <svg className="h-4 w-4 text-indigo-500" fill="currentColor" viewBox="0 0 20 20">
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                      {feature}
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => handleSelect(plan.tier)}
                  disabled={isCurrent || updatePlan.isPending}
                  className={`mt-6 w-full rounded py-2 text-sm font-medium ${
                    isCurrent
                      ? "cursor-default bg-gray-100 text-gray-500"
                      : plan.highlighted
                        ? "bg-indigo-600 text-white hover:bg-indigo-700"
                        : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  {isCurrent ? "Current Plan" : "Select Plan"}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
