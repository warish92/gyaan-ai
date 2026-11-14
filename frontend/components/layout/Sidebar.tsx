"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Layers,
  GraduationCap,
  BookOpen,
  Compass,
  Activity,
  Library,
  CheckSquare,
  TrendingUp,
  HeartHandshake,
  Cpu,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  X,
  User,
  LogIn,
  ShieldCheck,
} from "lucide-react";
import { IconButton } from "../ui/IconButton";
import { Badge } from "../ui/Badge";
import { useAuth } from "../auth/AuthContext";

export interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  tag?: string;
  tagVariant?: "primary" | "ai" | "teal" | "neutral" | "warning";
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const navigationGroups: NavGroup[] = [
  {
    title: "LEARNING CORE",
    items: [
      { name: "Overview", href: "/", icon: Layers },
      { name: "CBSE Curriculum", href: "/curriculum", icon: BookOpen, tag: "2026-27", tagVariant: "primary" },
      { name: "AI Teacher", href: "/teacher", icon: GraduationCap, tag: "Studio", tagVariant: "primary" },
      { name: "Learning Plans", href: "/learning-plans", icon: Compass, tag: "7-Day Plan", tagVariant: "primary" },
    ],
  },
  {
    title: "ASSESSMENT & RESOURCES",
    items: [
      { name: "Diagnostic", href: "/diagnostic", icon: Activity, tag: "Diagnostic", tagVariant: "teal" },
      { name: "Resources", href: "/resources", icon: Library, tag: "NCERT", tagVariant: "teal" },
      { name: "Practice & Assessments", href: "/practice", icon: CheckSquare, tag: "Quizzes", tagVariant: "teal" },
    ],
  },
  {
    title: "COACHING & SYSTEM",
    items: [
      { name: "My Progress", href: "/progress", icon: TrendingUp, tag: "Analytics", tagVariant: "ai" },
      { name: "AI Mentor", href: "/mentor", icon: HeartHandshake, tag: "Coach", tagVariant: "ai" },
      { name: "Agent Arena", href: "/agent-arena", icon: Cpu, tag: "Multi-Agent", tagVariant: "ai" },
    ],
  },
];

export interface SidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isCollapsed,
  onToggleCollapse,
  isMobileOpen = false,
  onCloseMobile,
}) => {
  const pathname = usePathname();
  const { student, isAuthenticated } = useAuth();

  const isRouteActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  const navContent = (
    <div className="flex flex-col h-full bg-white select-none">
      {/* Brand Header */}
      <div
        className={`h-16 flex items-center border-b border-[#E2E8F0] px-4 transition-all duration-200 ${
          isCollapsed ? "justify-center" : "justify-between"
        }`}
      >
        <Link
          href="/"
          onClick={onCloseMobile}
          className="flex items-center gap-3 group focus:outline-none"
        >
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-xs shrink-0 group-hover:bg-blue-700 transition-colors">
            <Sparkles className="w-5 h-5" />
          </div>
          {!isCollapsed && (
            <div className="flex flex-col overflow-hidden">
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-base text-[#172033] tracking-tight whitespace-nowrap">
                  Gyaan AI
                </span>
                <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-blue-100 text-[#2563EB] uppercase tracking-wider">
                  CBSE 10
                </span>
              </div>
              <span className="text-[11px] text-[#64748B] truncate">Multi-Agent Workspace</span>
            </div>
          )}
        </Link>

        {/* Mobile close button */}
        {onCloseMobile && (
          <button
            onClick={onCloseMobile}
            className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100"
            aria-label="Close navigation"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Navigation Groups */}
      <div className="flex-1 overflow-y-auto py-4 px-3 space-y-6">
        {navigationGroups.map((group, groupIdx) => (
          <div key={groupIdx} className="space-y-1">
            {!isCollapsed ? (
              <h4 className="px-3 text-[11px] font-semibold text-[#94A3B8] tracking-wider uppercase mb-1.5">
                {group.title}
              </h4>
            ) : (
              <div className="h-2" />
            )}
            <ul className="space-y-1">
              {group.items.map((item) => {
                const active = isRouteActive(item.href);
                const Icon = item.icon;

                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onCloseMobile}
                      title={isCollapsed ? item.name : undefined}
                      className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
                        active
                          ? "bg-[#EFF6FF] text-[#2563EB] font-semibold shadow-xs"
                          : "text-[#64748B] hover:text-[#172033] hover:bg-slate-50"
                      } ${isCollapsed ? "justify-center px-2" : ""}`}
                    >
                      <Icon
                        className={`w-5 h-5 shrink-0 transition-colors ${
                          active ? "text-[#2563EB]" : "text-slate-400 group-hover:text-slate-600"
                        }`}
                      />
                      {!isCollapsed && (
                        <div className="flex items-center justify-between flex-1 truncate">
                          <span className="truncate">{item.name}</span>
                          {item.tag && (
                            <Badge
                              variant={item.tagVariant || "secondary"}
                              size="sm"
                              className="ml-auto text-[10px] py-0 px-1.5 scale-90"
                            >
                              {item.tag}
                            </Badge>
                          )}
                        </div>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      {/* Student Profile Quick Access / Auth Prompt */}
      {!isCollapsed && (
        <div className="px-3 py-2 border-t border-[#F1F5F9]">
          {isAuthenticated && student ? (
            <Link
              href="/profile"
              onClick={onCloseMobile}
              className="flex items-center gap-2.5 p-2 rounded-xl bg-slate-50 hover:bg-blue-50/60 transition-colors group"
            >
              <div className="w-7 h-7 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold shrink-0">
                {student.display_name.charAt(0).toUpperCase()}
              </div>
              <div className="flex flex-col truncate">
                <span className="text-xs font-semibold text-[#172033] truncate group-hover:text-blue-700">
                  {student.display_name}
                </span>
                <span className="text-[10px] text-emerald-600 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> {student.grade}
                </span>
              </div>
            </Link>
          ) : (
            <Link
              href="/login"
              onClick={onCloseMobile}
              className="flex items-center justify-between p-2 rounded-xl bg-slate-50 hover:bg-blue-50 text-xs font-medium text-slate-700 hover:text-blue-700 transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <LogIn className="w-3.5 h-3.5 text-blue-600" />
                Sign in to save scores
              </span>
              <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
            </Link>
          )}
        </div>
      )}

      {/* Collapse Footer Toggle (Desktop only) */}
      <div className="p-3 border-t border-[#E2E8F0] hidden md:flex items-center justify-between">
        {!isCollapsed && (
          <div className="flex items-center gap-2 text-xs text-[#64748B]">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" />
            <span>Local Ollama Mode</span>
          </div>
        )}
        <IconButton
          variant="ghost"
          size="sm"
          ariaLabel={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          onClick={onToggleCollapse}
          className={isCollapsed ? "mx-auto" : ""}
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </IconButton>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={`hidden md:flex flex-col border-r border-[#E2E8F0] h-screen sticky top-0 bg-white transition-[width] duration-200 z-30 shrink-0 ${
          isCollapsed ? "w-20" : "w-64"
        }`}
      >
        {navContent}
      </aside>

      {/* Mobile Drawer Backdrop & Slide-in */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
            onClick={onCloseMobile}
            aria-hidden="true"
          />

          {/* Drawer container */}
          <div className="relative flex-1 flex flex-col max-w-xs w-full bg-white shadow-2xl z-10">
            {navContent}
          </div>
        </div>
      )}
    </>
  );
};
