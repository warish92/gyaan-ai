import React from "react";

export type BadgeVariant =
  | "primary"
  | "secondary"
  | "success"
  | "warning"
  | "error"
  | "ai"
  | "teal"
  | "neutral";

export type BadgeSize = "sm" | "md";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  icon?: React.ReactNode;
}

const variantStyles: Record<BadgeVariant, { bg: string; text: string; border: string; dot: string }> = {
  primary: {
    bg: "bg-blue-50",
    text: "text-[#2563EB]",
    border: "border-blue-200",
    dot: "bg-[#2563EB]",
  },
  secondary: {
    bg: "bg-slate-100",
    text: "text-[#64748B]",
    border: "border-slate-200",
    dot: "bg-[#64748B]",
  },
  success: {
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    border: "border-emerald-200",
    dot: "bg-[#16A34A]",
  },
  warning: {
    bg: "bg-amber-50",
    text: "text-amber-700",
    border: "border-amber-200",
    dot: "bg-[#F59E0B]",
  },
  error: {
    bg: "bg-red-50",
    text: "text-red-700",
    border: "border-red-200",
    dot: "bg-[#DC2626]",
  },
  ai: {
    bg: "bg-purple-50",
    text: "text-[#7C5CFC]",
    border: "border-purple-200",
    dot: "bg-[#7C5CFC]",
  },
  teal: {
    bg: "bg-teal-50",
    text: "text-teal-700",
    border: "border-teal-200",
    dot: "bg-[#0F9F9A]",
  },
  neutral: {
    bg: "bg-gray-100",
    text: "text-gray-700",
    border: "border-gray-200",
    dot: "bg-gray-500",
  },
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: "px-2 py-0.5 text-[11px] leading-tight",
  md: "px-2.5 py-1 text-xs leading-none",
};

export const Badge: React.FC<BadgeProps> = ({
  variant = "primary",
  size = "md",
  dot = false,
  icon,
  className = "",
  children,
  ...props
}) => {
  const styles = variantStyles[variant];

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${styles.bg} ${styles.text} ${styles.border} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${styles.dot} shrink-0`} />}
      {icon && <span className="shrink-0">{icon}</span>}
      <span>{children}</span>
    </span>
  );
};
