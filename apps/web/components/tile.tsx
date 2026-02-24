"use client";

import clsx from "clsx";
import { ReactNode } from "react";

interface TileProps {
  title: string;
  subtitle: string;
  selected?: boolean;
  dimmed?: boolean;
  onClick?: () => void;
  icon?: ReactNode;
  variant?: "default" | "pronote";
  className?: string;
  eyebrow?: string;
  extra?: ReactNode;
}

export function Tile({
  title,
  subtitle,
  selected = false,
  dimmed = false,
  onClick,
  icon,
  variant = "default",
  className,
  eyebrow,
  extra
}: TileProps) {
  const pronote = variant === "pronote";

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(event) => {
        if (!onClick) {
          return;
        }
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onClick();
        }
      }}
      className={clsx(
        "group relative overflow-hidden rounded-2xl border bg-white p-5 text-left transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-emerald-200",
        onClick ? "cursor-pointer" : "",
        pronote
          ? "hover:-translate-y-0.5 hover:border-emerald-500 hover:shadow-[0_14px_24px_rgba(7,125,108,0.22)]"
          : "hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-[0_12px_22px_rgba(8,120,105,0.16)]",
        selected
          ? pronote
            ? "border-2 border-emerald-700 bg-gradient-to-br from-emerald-100 via-emerald-50 to-[#fff6cf] shadow-[0_18px_30px_rgba(11,134,116,0.26)]"
            : "border-2 border-emerald-600 bg-gradient-to-br from-emerald-50 via-white to-teal-50 shadow-[0_16px_28px_rgba(8,120,105,0.18)]"
          : pronote
            ? "border-emerald-300 bg-gradient-to-br from-[#e5fbf6] via-[#f7fffc] to-[#fff9dc]"
            : "border-slate-300",
        dimmed && !selected ? "opacity-40 saturate-50 scale-[0.97] pointer-events-auto" : "",
        className
      )}
    >
      <span
        className={clsx(
          "absolute right-3 top-3 flex items-center gap-1 rounded-full border px-2.5 py-1 text-[0.7rem] font-bold tracking-wide transition-all duration-200",
          selected
            ? "border-emerald-500 bg-emerald-500 text-white shadow-[0_2px_8px_rgba(13,161,141,0.35)]"
            : "border-slate-200 bg-white/90 text-slate-400 shadow-sm backdrop-blur-sm"
        )}
      >
        {selected ? (
          <>
            <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
              <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Actif
          </>
        ) : (
          <>
            <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
              <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.5" />
              <path d="M6 4v4M4 6h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            Choisir
          </>
        )}
      </span>
      <div
        className={clsx(
          pronote ? "mb-3 text-4xl leading-none" : "mb-2 text-lg",
          pronote ? "text-emerald-700" : selected ? "text-emerald-700" : "text-teal-700"
        )}
      >
        {icon ?? "◆"}
      </div>
      {eyebrow && (
        <p className={clsx("mb-1 text-sm font-semibold tracking-wide", pronote ? "text-emerald-800" : "text-teal-800")}>
          {eyebrow}
        </p>
      )}
      <h3 className={clsx("font-semibold text-slate-900", pronote ? "text-[1.35rem]" : "text-[1.15rem]")}>{title}</h3>
      <p className="mt-1 text-base text-slate-700">{subtitle}</p>
      {extra && <div className="mt-3">{extra}</div>}
    </div>
  );
}
