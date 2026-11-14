import React from "react";

export interface StatusBadgeProps {
  status: "connected" | "degraded" | "disconnected" | "loading";
  label?: string;
  latencyMs?: number;
  compact?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  latencyMs,
  compact = false,
}) => {
  const configs = {
    connected: {
      bg: "bg-emerald-50",
      border: "border-emerald-200",
      text: "text-emerald-800",
      dot: "bg-emerald-500",
      defaultText: "Backend Connected",
      compactText: "Live",
    },
    degraded: {
      bg: "bg-amber-50",
      border: "border-amber-200",
      text: "text-amber-800",
      dot: "bg-amber-500",
      defaultText: "Backend Degraded",
      compactText: "Degraded",
    },
    disconnected: {
      bg: "bg-rose-50",
      border: "border-rose-200",
      text: "text-rose-800",
      dot: "bg-rose-500",
      defaultText: "Backend Offline",
      compactText: "Offline",
    },
    loading: {
      bg: "bg-blue-50",
      border: "border-blue-200",
      text: "text-blue-800",
      dot: "bg-blue-500 animate-pulse",
      defaultText: "Checking...",
      compactText: "...",
    },
  };

  const current = configs[status];
  const displayText = label || (compact ? current.compactText : current.defaultText);

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full font-medium border select-none ${
        compact ? "px-2 py-0.5 text-[11px]" : "px-3 py-1 text-xs"
      } ${current.bg} ${current.border} ${current.text}`}
      role="status"
    >
      <span className={`rounded-full shrink-0 ${compact ? "w-1.5 h-1.5" : "w-2 h-2"} ${current.dot}`} />
      <span className="truncate">{displayText}</span>
      {latencyMs !== undefined && status !== "loading" && !compact && (
        <span className="opacity-70 text-[10px]">({latencyMs}ms)</span>
      )}
    </div>
  );
};
