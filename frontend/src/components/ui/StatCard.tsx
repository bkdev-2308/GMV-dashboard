import type { LucideIcon } from "lucide-react";
import { cn } from "@/utils/cn";

interface StatCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  color: "blue" | "green" | "yellow" | "purple" | "red";
  subtitle?: string;
}

const colorMap = {
  blue: "bg-blue-50 text-blue-600",
  green: "bg-emerald-50 text-emerald-600",
  yellow: "bg-amber-50 text-amber-600",
  purple: "bg-purple-50 text-purple-600",
  red: "bg-red-50 text-red-600",
};

export function StatCard({ label, value, icon: Icon, color, subtitle }: StatCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-center gap-3">
        <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg", colorMap[color])}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-xs font-medium text-slate-500">{label}</p>
          <p className="text-lg font-bold text-slate-900">{value}</p>
          {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
        </div>
      </div>
    </div>
  );
}
