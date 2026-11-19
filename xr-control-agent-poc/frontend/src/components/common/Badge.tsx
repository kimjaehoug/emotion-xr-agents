import type { ReactNode } from "react";

type Tone = "neutral" | "teal" | "amber" | "rose" | "emerald" | "slate";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-600",
  teal: "bg-teal-50 text-teal-700 ring-1 ring-inset ring-teal-200",
  amber: "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200",
  rose: "bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-200",
  emerald: "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200",
  slate: "bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-200",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  );
}

const STATE_LEVEL_TONE: Record<string, Tone> = {
  NORMAL: "emerald",
  WATCH: "amber",
  ACTION_REQUIRED: "rose",
  UNKNOWN: "slate",
};

export function StateLevelBadge({ level }: { level: string }) {
  return <Badge tone={STATE_LEVEL_TONE[level] ?? "slate"}>{level}</Badge>;
}

export function PlannerSourceBadge({ source }: { source: string }) {
  const isFallback = source === "rule_based_fallback";
  return <Badge tone={isFallback ? "amber" : "teal"}>{isFallback ? "Fallback (규칙 기반)" : source}</Badge>;
}
