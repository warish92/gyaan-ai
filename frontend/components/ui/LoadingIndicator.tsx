import React from "react";
import { Loader2 } from "lucide-react";

export interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}

const spinnerSizes = {
  sm: "w-4 h-4",
  md: "w-6 h-6",
  lg: "w-8 h-8",
};

export const Spinner: React.FC<SpinnerProps> = ({ size = "md", className = "", label }) => {
  return (
    <div className="inline-flex items-center gap-2 text-[#2563EB]">
      <Loader2 className={`animate-spin ${spinnerSizes[size]} ${className}`} />
      {label && <span className="text-xs text-[#64748B] font-medium">{label}</span>}
    </div>
  );
};

export interface SkeletonProps {
  className?: string;
}

export const Skeleton: React.FC<SkeletonProps> = ({ className = "" }) => {
  return (
    <div
      className={`animate-pulse bg-slate-200/80 rounded-lg ${className}`}
      aria-hidden="true"
    />
  );
};

export interface LoadingCardProps {
  rows?: number;
  className?: string;
}

export const LoadingCard: React.FC<LoadingCardProps> = ({ rows = 3, className = "" }) => {
  return (
    <div className={`p-6 bg-white rounded-xl border border-[#E2E8F0] space-y-4 ${className}`}>
      <div className="flex items-center gap-3">
        <Skeleton className="w-10 h-10 rounded-lg" />
        <div className="space-y-1.5 flex-1">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      </div>
      <div className="space-y-2 pt-2">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-3 w-full" />
        ))}
      </div>
    </div>
  );
};
