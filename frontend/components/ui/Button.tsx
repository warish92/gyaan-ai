import React from "react";
import { Loader2 } from "lucide-react";

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "danger" | "ai";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-[#2563EB] text-white hover:bg-[#1D4ED8] focus:ring-blue-500 shadow-sm border border-transparent",
  secondary:
    "bg-white text-[#172033] hover:bg-slate-50 focus:ring-blue-400 border border-[#E2E8F0] shadow-sm",
  outline:
    "bg-transparent text-[#2563EB] hover:bg-blue-50 focus:ring-blue-400 border border-[#2563EB]/40",
  ghost:
    "bg-transparent text-[#64748B] hover:text-[#172033] hover:bg-slate-100 focus:ring-slate-300 border border-transparent",
  danger:
    "bg-[#DC2626] text-white hover:bg-red-700 focus:ring-red-400 shadow-sm border border-transparent",
  ai:
    "bg-[#7C5CFC] text-white hover:bg-[#6846EB] focus:ring-purple-400 shadow-sm border border-transparent",
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "px-2.5 py-1.5 text-xs rounded-lg gap-1.5",
  md: "px-4 py-2 text-sm rounded-lg gap-2",
  lg: "px-5 py-2.5 text-base rounded-xl gap-2.5",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      isLoading = false,
      leftIcon,
      rightIcon,
      disabled,
      className = "",
      children,
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || isLoading;

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        className={`inline-flex items-center justify-center font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-1 select-none ${
          variantStyles[variant]
        } ${sizeStyles[size]} ${
          isDisabled ? "opacity-50 cursor-not-allowed pointer-events-none" : "cursor-pointer active:scale-[0.98]"
        } ${className}`}
        {...props}
      >
        {isLoading && <Loader2 className="w-4 h-4 animate-spin shrink-0" />}
        {!isLoading && leftIcon && <span className="shrink-0">{leftIcon}</span>}
        {children && <span>{children}</span>}
        {!isLoading && rightIcon && <span className="shrink-0">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = "Button";
