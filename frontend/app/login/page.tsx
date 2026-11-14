"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogIn, Eye, EyeOff, ShieldCheck, AlertCircle, ArrowRight } from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { useAuth } from "../../components/auth/AuthContext";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If already authenticated, redirect to dashboard
  React.useEffect(() => {
    if (isAuthenticated) {
      router.push("/");
    }
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) {
      setError("Please enter your registered email address.");
      return;
    }

    if (!password) {
      setError("Please enter your password.");
      return;
    }

    setIsSubmitting(true);
    try {
      await login({
        email: cleanEmail,
        password,
      });
      router.push("/");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Invalid email or password. Please try again.";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-md mx-auto py-8 sm:py-12 space-y-6">
      <div className="text-center space-y-2">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[#2563EB] to-[#7C5CFC] text-white flex items-center justify-center mx-auto shadow-md">
          <LogIn className="w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-[#172033]">
          Sign In to Gyaan AI
        </h1>
        <p className="text-xs text-[#64748B] max-w-sm mx-auto">
          Access your personal CBSE learning dashboard, assessment scores, and AI tutoring history.
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

          {/* Email */}
          <div className="space-y-1">
            <label className="text-xs font-semibold text-[#172033]" htmlFor="email">
              Email Address
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
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
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

          <div className="pt-2">
            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={isSubmitting}
              className="w-full"
              rightIcon={<ArrowRight className="w-4 h-4" />}
            >
              Sign In
            </Button>
          </div>

          <div className="text-center pt-2">
            <p className="text-xs text-[#64748B]">
              New to Gyaan AI?{" "}
              <Link
                href="/register"
                className="font-semibold text-[#2563EB] hover:text-[#1D4ED8] transition-colors"
              >
                Create an account
              </Link>
            </p>
          </div>
        </form>
      </Card>

      <div className="flex items-center justify-center gap-2 text-xs text-slate-400">
        <ShieldCheck className="w-4 h-4 text-emerald-600" />
        <span>7-day persistent session &bull; Zero password leakage &bull; Isolated student data</span>
      </div>
    </div>
  );
}
