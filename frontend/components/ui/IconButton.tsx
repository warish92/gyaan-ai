import React from "react";

export type IconButtonVariant = "default" | "primary" | "ghost" | "outline";
export type IconButtonSize = "sm" | "md" | "lg";

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: IconButtonVariant;
  size?: IconButtonSize;
  ariaLabel: string;
}

const variantStyles: Record<IconButtonVariant, string> = {
  default:
    "bg-white text-[#64748B] hover:text-[#172033] hover:bg-slate-50 border border-[#E2E8F0] shadow-sm",
  primary:
    "bg-[#2563EB] text-white hover:bg-[#1D4ED8] border border-transparent shadow-sm",
  ghost:
    "bg-transparent text-[#64748B] hover:text-[#172033] hover:bg-slate-100 border border-transparent",
  outline:
    "bg-transparent text-[#64748B] hover:text-[#2563EB] hover:bg-blue-50 border border-[#E2E8F0]",
};

const sizeStyles: Record<IconButtonSize, string> = {
  sm: "p-1.5 text-xs rounded-lg min-w-[32px] min-h-[32px]",
  md: "p-2 text-sm rounded-lg min-w-[38px] min-h-[38px]",
  lg: "p-2.5 text-base rounded-xl min-w-[44px] min-h-[44px]",
};

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    {
      variant = "default",
      size = "md",
      ariaLabel,
      className = "",
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        aria-label={ariaLabel}
        title={ariaLabel}
        disabled={disabled}
        className={`inline-flex items-center justify-center transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-1 select-none ${
          variantStyles[variant]
        } ${sizeStyles[size]} ${
          disabled ? "opacity-50 cursor-not-allowed pointer-events-none" : "cursor-pointer active:scale-95"
        } ${className}`}
        {...props}
      >
        {children}
      </button>
    );
  }
);

IconButton.displayName = "IconButton";
