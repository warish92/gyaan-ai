import React from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  icon?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  breadcrumbs,
  badge,
  actions,
  icon,
}) => {
  return (
    <div className="mb-6 space-y-2">
      {/* Breadcrumbs */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-[#64748B]">
          {breadcrumbs.map((bc, idx) => {
            const isLast = idx === breadcrumbs.length - 1;
            return (
              <React.Fragment key={idx}>
                {idx > 0 && <ChevronRight className="w-3 h-3 text-slate-400 shrink-0" />}
                {bc.href && !isLast ? (
                  <Link
                    href={bc.href}
                    className="hover:text-[#2563EB] transition-colors font-medium"
                  >
                    {bc.label}
                  </Link>
                ) : (
                  <span className={isLast ? "text-[#172033] font-semibold" : ""}>{bc.label}</span>
                )}
              </React.Fragment>
            );
          })}
        </nav>
      )}

      {/* Main title & action row */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            {icon && <div className="text-[#2563EB] shrink-0">{icon}</div>}
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#172033]">{title}</h1>
            {badge && <div className="shrink-0">{badge}</div>}
          </div>
          {description && (
            <p className="text-sm text-[#64748B] max-w-3xl leading-relaxed">{description}</p>
          )}
        </div>

        {actions && <div className="flex items-center gap-2.5 shrink-0">{actions}</div>}
      </div>
    </div>
  );
};
