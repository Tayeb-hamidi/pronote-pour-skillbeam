"use client";

import clsx from "clsx";

interface StepperProps {
  current: number;
  labels: string[];
}

export function Stepper({ current, labels }: StepperProps) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-5">
      {labels.map((label, index) => {
        const step = index + 1;
        const active = step === current;
        const done = step < current;
        return (
          <div
            key={label}
            className={clsx(
              "relative overflow-hidden rounded-2xl border px-3 py-3 text-center transition",
              "before:absolute before:left-0 before:top-0 before:h-full before:w-1.5 before:rounded-l-2xl before:content-['']",
              active &&
                "border-emerald-500 bg-gradient-to-br from-emerald-100 to-emerald-50 text-emerald-950 shadow-[0_12px_24px_rgba(6,130,103,0.2)] before:bg-emerald-500",
              done && "border-emerald-300 bg-emerald-50 text-emerald-900 before:bg-emerald-500",
              !active && !done && "border-slate-300 bg-slate-100 text-slate-900 before:bg-slate-400"
            )}
          >
            <div className="text-lg font-semibold leading-none">{step}</div>
            <div className="mt-1 text-base font-semibold">{label}</div>
          </div>
        );
      })}
    </div>
  );
}
