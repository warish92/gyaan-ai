"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Menu, RefreshCw, User, ShieldCheck, LogOut, LogIn, UserPlus, Settings } from "lucide-react";
import { StatusBadge } from "../ui/StatusBadge";
import { IconButton } from "../ui/IconButton";
import { Button } from "../ui/Button";
import { HealthResponse } from "../../types";
import { useAuth } from "../auth/AuthContext";

export interface TopNavProps {
  health: HealthResponse | null;
  loading: boolean;
  latencyMs?: number;
  onRefresh?: () => void;
  onToggleMobileMenu: () => void;
}

const routeTitles: Record<string, { title: string; category: string }> = {
  "/": { title: "System Overview", category: "Workspace" },
  "/login": { title: "Student Login", category: "Account" },
  "/register": { title: "Student Registration", category: "Account" },
  "/profile": { title: "Student Profile", category: "Account" },
  "/curriculum": { title: "CBSE Class 10 Curriculum", category: "Learning Core" },
  "/teacher": { title: "AI Teacher Studio", category: "Learning Core" },
  "/learning-plans": { title: "Personalized Learning Plans", category: "Learning Core" },
  "/diagnostic": { title: "Knowledge Gap Diagnostic", category: "Assessment & Resources" },
  "/resources": { title: "NCERT Educational Resources", category: "Assessment & Resources" },
  "/documents": { title: "Document Library & Notes", category: "Assessment & Resources" },
  "/practice": { title: "Practice & Assessments", category: "Assessment & Resources" },
  "/progress": { title: "My Progress & Analytics", category: "Coaching & System" },
  "/mentor": { title: "AI Mentor & Coach", category: "Coaching & System" },
  "/agent-arena": { title: "Multi-Agent Routing Arena", category: "Coaching & System" },
};

export const TopNav: React.FC<TopNavProps> = ({
  health,
  loading,
  latencyMs,
  onRefresh,
  onToggleMobileMenu,
}) => {
  const pathname = usePathname();
  const router = useRouter();
  const { student, isAuthenticated, logout } = useAuth();
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);

  const routeInfo = routeTitles[pathname] || { title: "Workspace", category: "Platform" };

  const getStatus = (): "connected" | "degraded" | "disconnected" | "loading" => {
    if (loading) return "loading";
    if (!health) return "disconnected";
    if (health.status === "healthy" && health.ollama_connected) return "connected";
    if (health.status === "degraded" || !health.ollama_connected) return "degraded";
    return "connected";
  };

  const handleLogout = async () => {
    setProfileDropdownOpen(false);
    await logout();
    router.push("/");
  };

  return (
    <header className="sticky top-0 z-20 w-full bg-white/95 backdrop-blur-md border-b border-[#E2E8F0] h-16 flex items-center px-4 sm:px-6">
      <div className="flex items-center justify-between w-full">
        {/* Left: Mobile hamburger & dynamic page title */}
        <div className="flex items-center gap-3">
          <IconButton
            variant="ghost"
            size="md"
            ariaLabel="Open navigation menu"
            onClick={onToggleMobileMenu}
            className="md:hidden"
          >
            <Menu className="w-5 h-5 text-[#172033]" />
          </IconButton>

          <div className="flex flex-col">
            <span className="text-[11px] font-semibold tracking-wider uppercase text-[#64748B] hidden sm:inline">
              {routeInfo.category}
            </span>
            <h2 className="text-base sm:text-lg font-bold text-[#172033] tracking-tight">
              {routeInfo.title}
            </h2>
          </div>
        </div>

        {/* Right: Live Backend Status & Authentication Controls */}
        <div className="flex items-center gap-3 sm:gap-4">
          {/* Backend Status Badge */}
          <div className="flex items-center gap-1.5">
            <StatusBadge status={getStatus()} latencyMs={latencyMs} compact={false} />
            {onRefresh && (
              <button
                onClick={onRefresh}
                disabled={loading}
                title="Refresh backend status"
                className="p-1.5 text-slate-400 hover:text-[#172033] hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-40"
                aria-label="Refresh status"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              </button>
            )}
          </div>

          <div className="h-6 w-[1px] bg-[#E2E8F0] hidden sm:block" />

          {/* Authentication State */}
          {isAuthenticated && student ? (
            /* Authenticated Student Profile & Actions */
            <div className="relative">
              <button
                onClick={() => setProfileDropdownOpen((prev) => !prev)}
                className="flex items-center gap-2.5 p-1 rounded-xl hover:bg-slate-100 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400"
                aria-label="Student profile menu"
              >
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-semibold shadow-xs">
                  {student.display_name.charAt(0).toUpperCase()}
                </div>
                <div className="hidden lg:flex flex-col text-left">
                  <span className="text-xs font-semibold text-[#172033] leading-none truncate max-w-[120px]">
                    {student.display_name}
                  </span>
                  <span className="text-[10px] text-[#64748B] mt-0.5 flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3 text-emerald-600" />
                    {student.grade}
                  </span>
                </div>
              </button>

              {/* Profile Dropdown Menu */}
              {profileDropdownOpen && (
                <>
                  <div
                    className="fixed inset-0 z-30"
                    onClick={() => setProfileDropdownOpen(false)}
                  />
                  <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-lg border border-[#E2E8F0] py-2 z-40 text-xs">
                    <div className="px-4 py-2 border-b border-slate-100">
                      <p className="font-semibold text-[#172033] truncate">{student.display_name}</p>
                      <p className="text-[11px] text-[#64748B] truncate">{student.email}</p>
                      <p className="text-[10px] text-blue-600 font-medium mt-1">
                        ID: {student.id}
                      </p>
                    </div>

                    <Link
                      href="/profile"
                      onClick={() => setProfileDropdownOpen(false)}
                      className="flex items-center gap-2 px-4 py-2 hover:bg-slate-50 text-slate-700 font-medium"
                    >
                      <Settings className="w-4 h-4 text-slate-400" />
                      <span>Manage Profile</span>
                    </Link>

                    <Link
                      href="/"
                      onClick={() => setProfileDropdownOpen(false)}
                      className="flex items-center gap-2 px-4 py-2 hover:bg-slate-50 text-slate-700 font-medium"
                    >
                      <ShieldCheck className="w-4 h-4 text-emerald-500" />
                      <span>My Learning Dashboard</span>
                    </Link>

                    <div className="border-t border-slate-100 mt-1 pt-1">
                      <button
                        onClick={handleLogout}
                        className="w-full text-left flex items-center gap-2 px-4 py-2 hover:bg-red-50 text-red-600 font-medium"
                      >
                        <LogOut className="w-4 h-4 text-red-500" />
                        <span>Sign Out</span>
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          ) : (
            /* Unauthenticated Visitor Options */
            <div className="flex items-center gap-2">
              <Link href="/login">
                <Button variant="ghost" size="sm" leftIcon={<LogIn className="w-3.5 h-3.5" />}>
                  Sign In
                </Button>
              </Link>
              <Link href="/register">
                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={<UserPlus className="w-3.5 h-3.5" />}
                  className="hidden sm:inline-flex"
                >
                  Register
                </Button>
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
