import React from "react";
import { LucideIcon, Sparkles } from "lucide-react";
import { Badge } from "./Badge";

export interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  agentInfo?: {
    name: string;
    role: string;
    phase: string;
    status: string;
  };
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon,
  title,
  description,
  action,
  agentInfo,
  className = "",
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center p-8 sm:p-12 bg-white rounded-2xl border border-[#E2E8F0] shadow-sm ${className}`}
    >
      <div className="w-16 h-16 rounded-2xl bg-blue-50 text-[#2563EB] flex items-center justify-center mb-5 shadow-sm border border-blue-100">
        <Icon className="w-8 h-8" />
      </div>

      <h3 className="text-xl font-bold text-[#172033] mb-2">{title}</h3>
      <p className="text-sm text-[#64748B] max-w-md leading-relaxed mb-6">{description}</p>

      {agentInfo && (
        <div className="w-full max-w-md mb-6 p-4 rounded-xl bg-slate-50 border border-slate-200 text-left space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-[#172033]">
              <Sparkles className="w-3.5 h-3.5 text-[#7C5CFC]" />
              <span>Assigned AI Agent: {agentInfo.name}</span>
            </div>
            <Badge variant="ai" size="sm">
              {agentInfo.phase}
            </Badge>
          </div>
          <p className="text-xs text-[#64748B]">{agentInfo.role}</p>
          <div className="pt-1.5 border-t border-slate-200 flex items-center justify-between text-[11px] text-[#64748B]">
            <span>Integration Status:</span>
            <Badge variant="warning" size="sm" dot>
              {agentInfo.status}
            </Badge>
          </div>
        </div>
      )}

      {action && <div className="flex items-center gap-3">{action}</div>}
    </div>
  );
};
