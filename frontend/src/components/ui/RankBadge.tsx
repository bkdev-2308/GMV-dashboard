import { cn } from "@/utils/cn";

interface RankBadgeProps {
  rank: number;
}

export function RankBadge({ rank }: RankBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold",
        rank === 1 && "bg-gradient-to-br from-amber-100 to-amber-200 text-amber-800",
        rank === 2 && "bg-gradient-to-br from-slate-100 to-slate-200 text-slate-700",
        rank === 3 && "bg-gradient-to-br from-orange-100 to-orange-200 text-orange-800",
        rank > 3 && "bg-slate-100 text-slate-500"
      )}
    >
      {rank}
    </span>
  );
}
