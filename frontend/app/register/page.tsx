"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { UserPlus, Eye, EyeOff, ShieldCheck, AlertCircle, ArrowRight, Sparkles } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { useAuth } from "../../components/auth/AuthContext";

export default function RegisterPage() {
  const router = useRouter();
  const { register, isAuthenticated, isLoading: authLoading } = useAuth();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [grade, setGrade] = useState("Class 10");
  const [preferredLanguage, setPreferredLanguage] = useState("English");
  const [showPassword, setShowPassword] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If already authenticated, redirect to home
  React.useEffect(() => {
    if (isAuthenticated) {
      router.push("/");
    }
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    const cleanName = displayName.trim();
    if (!cleanName || cleanName.length < 2) {
      setError("Please enter your full name (at least 2 characters).");
      return;
    }

    const cleanEmail = email.trim().toLowerCase();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!cleanEmail || !emailRegex.test(cleanEmail)) {
      setError("Please enter a valid email address.");
      return;
    }

    if (!password || password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    setIsSubmitting(true);
    try {
      await register({
        display_name: cleanName,
        email: cleanEmail,
        password,
        grade,
        preferred_language: preferredLanguage,
      });
      router.push("/");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Registration failed. Please try again.";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-md mx-auto py-6 sm:py-10 space-y-6">
      <div className="text-center space-y-2">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[#2563EB] to-[#7C5CFC] text-white flex items-center justify-center mx-auto shadow-md">
          <UserPlus className="w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-[#172033]">
          Create Student Account
        </h1>
        <p className="text-xs text-[#64748B] max-w-sm mx-auto">
          Save your learning plans, quiz scores, topic mastery, and diagnostic history across sessions.
        </p>
      </div>

      <Card className="p-6 shadow-sm border-[#E2E8F0]">
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
              <div className="leading-relaxed">{error}</div>
            </div>
          )}

          {/* Full Name */}
          <div className="space-y-1">
            <label className="text-xs font-semibold text-[#172033]" htmlFor="display-name">
              Full Name <span className="text-red-500">*</span>
            </label>
            <input
              id="display-name"
              type="text"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Rohan Sharma"
              disabled={isSubmitting}
              className="w-full px-3 py-2 text-sm rounded-lg border border-[#E2E8F0] focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
            />
          </div>

          {/* Email */}
          <div className="space-y-1">
            <label className="text-xs font-semibold text-[#172033]" htmlFor="email">
              Email Address <span className="text-red-500">*</span>
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="student@example.com"
              disabled={isSubmitting}
              className="w-full px-3 py-2 text-sm rounded-lg border border-[#E2E8F0] focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
            />
          </div>

          {/* Password */}
          <div className="space-y-1">
            <label className="text-xs font-semibold text-[#172033]" htmlFor="password">
              Password <span className="text-red-500">*</span> (min 6 characters)
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                disabled={isSubmitting}
                className="w-full px-3 py-2 text-sm rounded-lg border border-[#E2E8F0] focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 focus:outline-none"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Grade & Language Row */}
          <div className="grid grid-cols-2 gap-3 pt-1">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-[#172033]" htmlFor="grade">
                Academic Grade
              </label>
              <select
                id="grade"
                value={grade}
                onChange={(e) => setGrade(e.target.value)}
                disabled={isSubmitting}
                className="w-full px-3 py-2 text-sm rounded-lg border border-[#E2E8F0] bg-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              >
                <option value="Class 10">Class 10 (CBSE)</option>
                <option value="Class 9">Class 9 (CBSE)</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-[#172033]" htmlFor="language">
                Language
              </label>
              <select
                id="language"
                value={preferredLanguage}
                onChange={(e) => setPreferredLanguage(e.target.value)}
                disabled={isSubmitting}
                className="w-full px-3 py-2 text-sm rounded-lg border border-[#E2E8F0] bg-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              >
                <option value="English">English</option>
                <option value="Hindi">Hindi</option>
              </select>
            </div>
          </div>

          <div className="pt-2">
            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={isSubmitting}
              className="w-full"
              rightIcon={<ArrowRight className="w-4 h-4" />}
            >
              Register &amp; Start Learning
            </Button>
          </div>

          <div className="text-center pt-2">
            <p className="text-xs text-[#64748B]">
              Already registered?{" "}
              <Link
                href="/login"
                className="font-semibold text-[#2563EB] hover:text-[#1D4ED8] transition-colors"
              >
                Sign in here
              </Link>
            </p>
          </div>
        </form>
      </Card>

      <div className="flex items-center justify-center gap-2 text-xs text-slate-400">
        <ShieldCheck className="w-4 h-4 text-emerald-600" />
        <span>Secure scrypt hashing &bull; Persistent SQLite storage &bull; Isolated records</span>
      </div>
    </div>
  );
}
