import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { BarChart3 } from "lucide-react";

interface OverviewData {
  engaged_viewers: number;
  comments: number;
  atc: number;
  views: number;
  avg_view_time: string;
  comments_rate: string;
  gpm: string;
  placed_order: number;
  abs: string;
  viewers: number;
  pcu: number;
  ctr: string;
  co: string;
  buyers: number;
  placed_items_sold: number;
}

interface OverviewMetricsProps {
  sessionId: string;
}

function fmt(val: number | string | null | undefined): string {
  if (val == null) return "-";
  if (typeof val === "string") return val || "-";
  return val.toLocaleString("vi-VN");
}

export function OverviewMetrics({ sessionId }: OverviewMetricsProps) {
  const { data } = useQuery({
    queryKey: ["overview-live", sessionId],
    queryFn: () =>
      api.get<{ success: boolean; data: OverviewData | null }>(`/api/overview/live?session_id=${sessionId}`),
    enabled: !!sessionId,
  });

  const metrics = data?.success ? data.data : null;

  if (!metrics) return null;

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center gap-2 px-5 py-3">
        <BarChart3 className="h-5 w-5 text-slate-700" />
        <h2 className="text-base font-semibold text-slate-800">Overview Metrics</h2>
      </div>

      {/* 3 Big Cards */}
      <div className="grid grid-cols-3 gap-0 bg-gradient-to-r from-red-500 via-orange-500 to-amber-500 px-5 py-5">
        {[
          { label: "Người xem tương tác", value: fmt(metrics.engaged_viewers) },
          { label: "Tổng bình luận", value: fmt(metrics.comments) },
          { label: "Thêm vào giỏ hàng", value: fmt(metrics.atc) },
        ].map((item) => (
          <div key={item.label} className="rounded-lg bg-white/10 px-4 py-4 text-center">
            <p className="mb-2 text-[0.65rem] font-medium uppercase tracking-wider text-white/90">
              {item.label}
            </p>
            <p className="text-3xl font-bold leading-none text-white">{item.value}</p>
          </div>
        ))}
      </div>

      {/* Row 1: 6 small metrics */}
      <div className="grid grid-cols-6 divide-x divide-white/20 bg-gradient-to-r from-red-500 via-orange-500 to-amber-500 border-t border-white/20">
        {[
          { label: "Tổng lượt xem", value: fmt(metrics.views) },
          { label: "Số lượt xem trung bình", value: fmt(metrics.avg_view_time) },
          { label: "Tỷ lệ bình luận", value: fmt(metrics.comments_rate) },
          { label: "GPM (đ)", value: fmt(metrics.gpm) },
          { label: "Tổng đơn hàng", value: fmt(metrics.placed_order) },
          { label: "Giá trị đơn hàng trung bình", value: fmt(metrics.abs) },
        ].map((item) => (
          <div key={item.label} className="px-2 py-3 text-center">
            <p className="mb-1.5 text-[0.6rem] font-medium uppercase leading-tight tracking-wider text-white/85">
              {item.label}
            </p>
            <p className="text-lg font-bold leading-none text-white">{item.value}</p>
          </div>
        ))}
      </div>

      {/* Row 2: 6 small metrics */}
      <div className="grid grid-cols-6 divide-x divide-white/20 bg-gradient-to-r from-red-500 via-orange-500 to-amber-500 border-t border-white/20">
        {[
          { label: "Tổng người xem", value: fmt(metrics.viewers) },
          { label: "PCU", value: fmt(metrics.pcu) },
          { label: "Tỷ lệ click vào sản phẩm", value: fmt(metrics.ctr) },
          { label: "Tỷ lệ click để đặt hàng", value: fmt(metrics.co) },
          { label: "Người mua", value: fmt(metrics.buyers) },
          { label: "Các mặt hàng được bán", value: fmt(metrics.placed_items_sold) },
        ].map((item) => (
          <div key={item.label} className="px-2 py-3 text-center">
            <p className="mb-1.5 text-[0.6rem] font-medium uppercase leading-tight tracking-wider text-white/85">
              {item.label}
            </p>
            <p className="text-lg font-bold leading-none text-white">{item.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
