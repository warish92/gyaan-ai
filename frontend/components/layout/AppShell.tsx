"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { Sidebar } from "./Sidebar";
import { TopNav } from "./TopNav";
import { apiClient } from "../../lib/api";
import { HealthResponse } from "../../types";
import { AuthProvider } from "../auth/AuthContext";

export interface BackendHealthContextType {
  health: HealthResponse | null;
  loading: boolean;
  error: string | null;
  latencyMs?: number;
  lastChecked: string | null;
  refresh: () => Promise<void>;
}

const BackendHealthContext = createContext<BackendHealthContextType>({
  health: null,
  loading: true,
  error: null,
  latencyMs: undefined,
  lastChecked: null,
  refresh: async () => {},
});

export const useBackendHealth = () => useContext(BackendHealthContext);

export interface AppShellProps {
  children: React.ReactNode;
}

const AppShellContent: React.FC<AppShellProps> = ({ children }) => {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const [isMobileOpen, setIsMobileOpen] = useState<boolean>(false);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | undefined>(undefined);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiClient.checkConnectivity();
      setLatencyMs(result.latencyMs);
      setLastChecked(new Date().toLocaleTimeString());
      if (result.connected && result.health) {
        setHealth(result.health);
      } else {
        setError(result.error || "Backend reported degraded status or is unreachable.");
        setHealth(result.health || null);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to connect to backend.";
      setError(msg);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  const toggleCollapse = () => setIsCollapsed((prev) => !prev);
  const toggleMobileMenu = () => setIsMobileOpen((prev) => !prev);
  const closeMobileMenu = () => setIsMobileOpen(false);

  return (
    <BackendHealthContext.Provider
      value={{ health, loading, error, latencyMs, lastChecked, refresh: fetchHealth }}
    >
      <div className="min-h-screen flex bg-[#F7F9FC] text-[#172033]">
        {/* Left Sidebar */}
        <Sidebar
          isCollapsed={isCollapsed}
          onToggleCollapse={toggleCollapse}
          isMobileOpen={isMobileOpen}
          onCloseMobile={closeMobileMenu}
        />

        {/* Right Application Workspace Area */}
        <div className="flex-1 flex flex-col min-w-0 min-h-screen">
          {/* Top Navigation */}
          <TopNav
            health={health}
            loading={loading}
            latencyMs={latencyMs}
            onRefresh={fetchHealth}
            onToggleMobileMenu={toggleMobileMenu}
          />

          {/* Main Content Area */}
          <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
            {children}
          </main>
        </div>
      </div>
    </BackendHealthContext.Provider>
  );
};

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  return (
    <AuthProvider>
      <AppShellContent>{children}</AppShellContent>
    </AuthProvider>
  );
};
