"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  StudentProfileResponse,
  StudentLoginRequest,
  StudentRegisterRequest,
  StudentProfileUpdateRequest,
  AuthTokenResponse,
} from "../../types";
import { apiClient, ApiError } from "../../lib/api";

export interface AuthContextType {
  student: StudentProfileResponse | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  authError: string | null;
  login: (credentials: StudentLoginRequest) => Promise<void>;
  register: (data: StudentRegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (data: StudentProfileUpdateRequest) => Promise<void>;
  clearError: () => void;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  student: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  authError: null,
  login: async () => {},
  register: async () => {},
  logout: async () => {},
  updateProfile: async () => {},
  clearError: () => {},
  refreshProfile: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export const AUTH_TOKEN_KEY = "gyaan_auth_token";

export interface AuthProviderProps {
  children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [student, setStudent] = useState<StudentProfileResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [authError, setAuthError] = useState<string | null>(null);

  // Restore session from HttpOnly cookie or localStorage on initial mount
  const restoreSession = useCallback(async () => {
    setIsLoading(true);
    setAuthError(null);
    try {
      if (typeof window !== "undefined") {
        const storedToken = localStorage.getItem(AUTH_TOKEN_KEY);
        try {
          // Attempt profile retrieval via HttpOnly cookie or stored Bearer token
          const profile = await apiClient.getProfile(storedToken || undefined);
          setStudent(profile);
          if (storedToken) {
            setToken(storedToken);
          }
        } catch {
          if (storedToken) {
            localStorage.removeItem(AUTH_TOKEN_KEY);
          }
          setStudent(null);
          setToken(null);
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  const login = async (credentials: StudentLoginRequest) => {
    setIsLoading(true);
    setAuthError(null);
    try {
      const response: AuthTokenResponse = await apiClient.login(credentials);
      if (typeof window !== "undefined") {
        localStorage.setItem(AUTH_TOKEN_KEY, response.token);
      }
      setToken(response.token);
      setStudent(response.student);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to authenticate student.";
      setAuthError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (data: StudentRegisterRequest) => {
    setIsLoading(true);
    setAuthError(null);
    try {
      const response: AuthTokenResponse = await apiClient.register(data);
      if (typeof window !== "undefined") {
        localStorage.setItem(AUTH_TOKEN_KEY, response.token);
      }
      setToken(response.token);
      setStudent(response.student);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to register student account.";
      setAuthError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      if (token) {
        await apiClient.logout(token).catch(() => {});
      }
    } finally {
      if (typeof window !== "undefined") {
        localStorage.removeItem(AUTH_TOKEN_KEY);
      }
      setToken(null);
      setStudent(null);
      setIsLoading(false);
    }
  };

  const updateProfile = async (data: StudentProfileUpdateRequest) => {
    setIsLoading(true);
    setAuthError(null);
    try {
      const updated = await apiClient.updateProfile(data, token);
      setStudent(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update profile.";
      setAuthError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const refreshProfile = async () => {
    if (!token) return;
    try {
      const profile = await apiClient.getProfile(token);
      setStudent(profile);
    } catch {
      // Ignored
    }
  };

  const clearError = () => setAuthError(null);

  return (
    <AuthContext.Provider
      value={{
        student,
        token,
        isAuthenticated: !!student && !!token,
        isLoading,
        authError,
        login,
        register,
        logout,
        updateProfile,
        clearError,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
