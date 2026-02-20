import React, { useRef, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { getUsageMetrics, type UsageDataPoint } from "../../services/analytics";

interface UsageChartProps {
  workspaceId?: string;
  period?: "day" | "week" | "month";
}

export default function UsageChart({ workspaceId, period = "week" }: UsageChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const { data: usageData, isLoading } = useQuery({
    queryKey: ["usage-chart", workspaceId, period],
    queryFn: () =>
      getUsageMetrics({
        workspaceId: workspaceId ?? "all",
        period,
      }),
  });

  const drawChart = useCallback((canvas: HTMLCanvasElement, data: UsageDataPoint[]) => {
    const ctx = canvas.getContext("2d");
    if (!ctx || data.length === 0) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const padding = { top: 20, right: 20, bottom: 40, left: 60 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Compute scales
    const maxCalls = Math.max(...data.map((d) => d.apiCalls), 1);
    const xStep = chartWidth / (data.length - 1 || 1);

    // Grid lines
    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = 1;
    const gridLines = 5;
    for (let i = 0; i <= gridLines; i++) {
      const y = padding.top + (chartHeight / gridLines) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left + chartWidth, y);
      ctx.stroke();

      // Y-axis labels
      const value = Math.round(maxCalls - (maxCalls / gridLines) * i);
      ctx.fillStyle = "#9ca3af";
      ctx.font = "11px sans-serif";
      ctx.textAlign = "right";
      ctx.fillText(value.toLocaleString(), padding.left - 8, y + 4);
    }

    // Draw API calls line
    ctx.beginPath();
    ctx.strokeStyle = "#6366f1";
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";

    data.forEach((point, i) => {
      const x = padding.left + i * xStep;
      const y = padding.top + chartHeight - (point.apiCalls / maxCalls) * chartHeight;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Fill area under curve
    const lastX = padding.left + (data.length - 1) * xStep;
    ctx.lineTo(lastX, padding.top + chartHeight);
    ctx.lineTo(padding.left, padding.top + chartHeight);
    ctx.closePath();
    ctx.fillStyle = "rgba(99, 102, 241, 0.08)";
    ctx.fill();

    // Data points
    data.forEach((point, i) => {
      const x = padding.left + i * xStep;
      const y = padding.top + chartHeight - (point.apiCalls / maxCalls) * chartHeight;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fillStyle = "#6366f1";
      ctx.fill();
    });

    // X-axis labels (show subset to avoid overlap)
    const labelInterval = Math.ceil(data.length / 7);
    ctx.fillStyle = "#9ca3af";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "center";
    data.forEach((point, i) => {
      if (i % labelInterval === 0 || i === data.length - 1) {
        const x = padding.left + i * xStep;
        const label = point.date.slice(5); // MM-DD
        ctx.fillText(label, x, height - 10);
      }
    });

    // Title
    ctx.fillStyle = "#6366f1";
    ctx.font = "bold 12px sans-serif";
    ctx.textAlign = "left";
    ctx.fillText("API Calls", padding.left, 14);
  }, []);

  useEffect(() => {
    if (canvasRef.current && usageData) {
      drawChart(canvasRef.current, usageData);
    }
  }, [usageData, drawChart]);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h2 className="mb-4 text-lg font-semibold text-gray-900">Usage Metrics</h2>
      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
        </div>
      ) : (
        <canvas
          ref={canvasRef}
          className="h-64 w-full"
          style={{ display: "block" }}
        />
      )}
    </div>
  );
}
