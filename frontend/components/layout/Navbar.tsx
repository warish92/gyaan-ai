import React from "react";
import { Sparkles, BookOpen, GraduationCap, Compass, Layers } from "lucide-react";
import { StatusBadge } from "../ui/StatusBadge";
import { HealthResponse } from "../../types";

export interface NavbarProps {
  health: HealthResponse | null;
  loading: boolean;
  latencyMs?: number;
  onRefresh?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ health, loading, latencyMs, onRefresh }) => {
  const getStatus = (): "connected" | "degraded" | "disconnected" | "loading" => {
    if (loading) return "loading";
    if (!health) return "disconnected";
    if (health.status === "healthy" && health.ollama_connected) return "connected";
    if (health.status === "degraded" || !health.ollama_connected) return "degraded";
    return "connected";
  };

  return (
    <header className="sticky top-0 z-40 w-full bg-white/90 backdrop-blur-md border-b border-[#E2E8F0]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#2563EB] to-[#7C5CFC] flex items-center justify-center text-white shadow-sm">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg text-[#172033] tracking-tight">Gyaan AI</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-[#2563EB]">
                CBSE Class 10
              </span>
            </div>
            <p className="text-xs text-[#64748B]">Multi-Agent Educational Platform</p>
          </div>
        </div>

        {/* Navigation placeholder */}
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-[#64748B]">
          <span className="text-[#2563EB] font-semibold flex items-center gap-1.5 cursor-default">
            <Layers className="w-4 h-4" /> System Overview
          </span>
          <span className="hover:text-[#172033] cursor-not-allowed opacity-60 flex items-center gap-1.5">
            <BookOpen className="w-4 h-4" /> AI Tutor
          </span>
          <span className="hover:text-[#172033] cursor-not-allowed opacity-60 flex items-center gap-1.5">
            <Compass className="w-4 h-4" /> Curriculum
          </span>
          <span className="hover:text-[#172033] cursor-not-allowed opacity-60 flex items-center gap-1.5">
            <GraduationCap className="w-4 h-4" /> Practice & Quizzes
          </span>
        </nav>

        {/* Real Backend Status Indicator */}
        <div className="flex items-center gap-3">
          <StatusBadge status={getStatus()} latencyMs={latencyMs} />
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={loading}
              title="Refresh connection status"
              className="p-1.5 rounded-lg border border-[#E2E8F0] text-[#64748B] hover:text-[#172033] hover:bg-slate-50 transition-colors disabled:opacity-50 text-xs font-medium"
            >
              Check
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
