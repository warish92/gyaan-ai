"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  User,
  ShieldCheck,
  Calendar,
  Mail,
  CheckCircle2,
  AlertCircle,
  Save,
  ArrowLeft,
  Key,
} from "lucide-react";
import { PageHeader } from "../../components/ui/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { useAuth } from "../../components/auth/AuthContext";

export default function ProfilePage() {
  const router = useRouter();
  const { student, isAuthenticated, isLoading: authLoading, updateProfile } = useAuth();

  const [displayName, setDisplayName] = useState("");
  const [grade, setGrade] = useState("Class 10");
  const [preferredLanguage, setPreferredLanguage] = useState("English");

  const [isSaving, setIsSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (student) {
      setDisplayName(student.display_name);
      setGrade(student.grade);
      setPreferredLanguage(student.preferred_language || "English");
    }
  }, [student]);

  if (authLoading) {
    return (
      <div className="py-12 text-center text-sm text-[#64748B]">
        Loading student profile...
      </div>
    );
  }

  if (!isAuthenticated || !student) {
    return (
      <div className="max-w-md mx-auto py-12 text-center space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-blue-50 text-[#2563EB] flex items-center justify-center mx-auto">
          <User className="w-6 h-6" />
        </div>
        <h2 className="text-xl font-bold text-[#172033]">Authentication Required</h2>
        <p className="text-xs text-[#64748B]">
          Please sign in or create an account to view and manage your student profile.
        </p>
        <div className="flex items-center justify-center gap-3 pt-2">
          <Link href="/login">
            <Button variant="primary" size="md">
              Sign In
            </Button>
          </Link>
          <Link href="/register">
            <Button variant="secondary" size="md">
              Register
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSuccessMsg(null);
    setErrorMsg(null);

    const cleanName = displayName.trim();
    if (!cleanName || cleanName.length < 2) {
      setErrorMsg("Display name must be at least 2 characters.");
      return;
    }

    setIsSaving(true);
    try {
      await updateProfile({
        display_name: cleanName,
        grade,
        preferred_language: preferredLanguage,
      });
      setSuccessMsg("Profile updated successfully!");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update profile.";
      setErrorMsg(msg);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <PageHeader
        title="Student Profile"
        description="Manage your academic preferences, display name, and verified account information."
        breadcrumbs={[{ label: "Account" }, { label: "Profile" }]}
        icon={<User className="w-7 h-7 text-[#2563EB]" />}
        badge={
          <Badge variant="success" size="md" dot>
            {student.account_status === "active" ? "Active Account" : student.account_status}
          </Badge>
        }
      />

      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Profile Card Sidebar */}
        <Card className="p-6 md:col-span-1 space-y-4 text-center">
          <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white text-2xl font-bold mx-auto shadow-sm">
            {student.display_name.charAt(0).toUpperCase()}
          </div>
          <div>
            <h3 className="font-bold text-base text-[#172033]">{student.display_name}</h3>
            <p className="text-xs text-[#64748B] mt-0.5">{student.email || "No email provided"}</p>
          </div>
          <div className="pt-3 border-t border-slate-100 text-left space-y-2 text-xs">
            <div className="flex items-center justify-between text-slate-500">
              <span>Student ID:</span>
              <span className="font-mono text-[#172033]">{student.id}</span>
            </div>
            <div className="flex items-center justify-between text-slate-500">
              <span>Joined:</span>
              <span className="text-[#172033]">
                {new Date(student.created_at).toLocaleDateString()}
              </span>
            </div>
            <div className="flex items-center justify-between text-slate-500">
              <span>Grade:</span>
              <span className="font-semibold text-blue-600">{student.grade}</span>
            </div>
          </div>
        </Card>

        {/* Profile Edit Form */}
        <Card className="p-6 md:col-span-2">
          <CardHeader className="p-0 pb-4">
            <CardTitle>Academic &amp; Profile Preferences</CardTitle>
            <CardDescription>
              Updates are saved immediately in the SQLite persistent database.
            </CardDescription>
          </CardHeader>

          <CardContent className="p-0 pt-4">
            <form onSubmit={handleSave} className="space-y-4">
              {/* Display Name */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-[#172033]" htmlFor="name">
                  Full Display Name
                </label>
                <input
                  id="name"
                  type="text"
                  required
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  disabled={isSaving}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-[#E2E8F0] focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>

              {/* Email (Read-only) */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-[#172033]" htmlFor="email-ro">
                  Email Address (Primary Identity)
                </label>
                <input
                  id="email-ro"
                  type="email"
                  disabled
                  value={student.email || ""}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-[#E2E8F0] bg-slate-50 text-slate-500 cursor-not-allowed"
                />
                <span className="text-[10px] text-slate-400 block">
                  Email address is permanently bound to this account for authentication.
                </span>
              </div>

              {/* Academic Grade */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[#172033]" htmlFor="grade-select">
                    Academic Grade
                  </label>
                  <select
                    id="grade-select"
                    value={grade}
                    onChange={(e) => setGrade(e.target.value)}
                    disabled={isSaving}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-[#E2E8F0] bg-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="Class 10">Class 10 (CBSE)</option>
                    <option value="Class 9">Class 9 (CBSE)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[#172033]" htmlFor="lang-select">
                    Explanation Language
                  </label>
                  <select
                    id="lang-select"
                    value={preferredLanguage}
                    onChange={(e) => setPreferredLanguage(e.target.value)}
                    disabled={isSaving}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-[#E2E8F0] bg-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="English">English</option>
                    <option value="Hindi">Hindi</option>
                  </select>
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                <Link href="/">
                  <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="w-4 h-4" />}>
                    Back to Dashboard
                  </Button>
                </Link>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={isSaving}
                  leftIcon={<Save className="w-4 h-4" />}
                >
                  Save Changes
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
