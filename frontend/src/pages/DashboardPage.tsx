import { useState, useMemo, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Link2,
  Star,
  RefreshCw,
  LogOut,
} from "lucide-react";
import { api } from "@/services/api";
import { authService } from "@/services/auth.service";
import { useSessionStore } from "@/store/session.store";
import { useToastStore } from "@/store/toast.store";
import { StatCard } from "@/components/ui/StatCard";
import { ProductTable } from "@/components/dashboard/ProductTable";
import { RevenueChart } from "@/components/dashboard/RevenueChart";
import { CategoryChart } from "@/components/dashboard/CategoryChart";
import { OverviewMetrics } from "@/components/dashboard/OverviewMetrics";
import { Spinner } from "@/components/ui/Spinner";
import { formatCurrency } from "@/utils/format";
import type { SessionDataResponse, SessionsResponse, TimeslotsResponse } from "@/types";

export function DashboardPage() {
  const { currentSessionId, setCurrentSession } = useSessionStore();
  const [selectedTimeslot, setSelectedTimeslot] = useState("");
  const [mappingMode, setMappingMode] = useState("dl_live");
  const queryClient = useQueryClient();
  const showToast = useToastStore((s) => s.showToast);

  // Active sessions
  const { data: sessionsData } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api.get<SessionsResponse>("/api/sessions"),
  });
  const sessions = sessionsData?.success ? sessionsData.sessions : [];

  // Auto-select first session if none selected
  useEffect(() => {
    if (!currentSessionId && sessions.length > 0) {
      setCurrentSession(sessions[0].session_id);
    }
  }, [sessions, currentSessionId, setCurrentSession]);

  // History timeslots for selected session
  const { data: timeslotsData } = useQuery({
    queryKey: ["timeslots", currentSessionId],
    queryFn: () => api.get<TimeslotsResponse>(`/api/history/timeslots?session_id=${currentSessionId}`),
    enabled: !!currentSessionId,
  });
  const timeslots = timeslotsData?.success ? timeslotsData.timeslots : [];

  // Data: live or history
  const isLive = !selectedTimeslot;
  const { data, isLoading } = useQuery({
    queryKey: isLive
      ? ["session-data", currentSessionId]
      : ["history-data", currentSessionId, selectedTimeslot],
    queryFn: () => {
      if (isLive) {
        const url = currentSessionId
          ? `/api/all-data?session_id=${currentSessionId}`
          : "/api/all-data";
        return api.get<SessionDataResponse>(url);
      }
      return api.get<SessionDataResponse>(
        `/api/history/data?session_id=${currentSessionId}&archived_at=${selectedTimeslot}`
      );
    },
    enabled: !!currentSessionId || isLive,
  });

  const stats = data?.stats;
  const products = data?.data ?? [];
  const lastSync = (data as SessionDataResponse)?.last_sync;


  // Computed stats
  const totalRevenue = stats?.total_revenue ?? 0;
  const totalNmv = stats?.total_confirmed_revenue ?? 0;
  const gap = totalRevenue - totalNmv;
  const withLink = stats?.with_link ?? 0;
  const totalProducts = stats?.total_products ?? products.length;
  const topGmv = useMemo(
    () => (products.length > 0 ? Math.max(...products.map((p) => p.revenue ?? 0)) : 0),
    [products]
  );

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["session-data"] });
    queryClient.invalidateQueries({ queryKey: ["history-data"] });
    showToast("Đang tải lại dữ liệu...", "info");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold text-slate-900">BeyondK Dashboard</h1>
        <div className="flex items-center gap-3">
          {lastSync && (
            <span className="flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              {lastSync}
            </span>
          )}
          <button
            onClick={handleRefresh}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Làm mới
          </button>
          <button
            onClick={() => authService.logout()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-red-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-600"
          >
            <LogOut className="h-3.5 w-3.5" />
            Đăng xuất
          </button>
        </div>
      </header>

      {/* Session Filter Card */}
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-slate-200 bg-white px-5 py-3">
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="7" width="20" height="15" rx="2" ry="2" />
              <polyline points="17 2 12 7 7 2" />
            </svg>
            Phiên Live
          </label>
          <select
            value={currentSessionId}
            onChange={(e) => {
              setCurrentSession(e.target.value);
              setSelectedTimeslot("");
            }}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">Chọn phiên</option>
            {sessions.map((s) => (
              <option key={s.session_id} value={s.session_id}>
                {s.session_title} ({s.item_count} SP)
              </option>
            ))}
          </select>
        </div>

        <div className="h-6 w-px bg-slate-200" />

        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            Khung giờ
          </label>
          <select
            value={selectedTimeslot}
            onChange={(e) => setSelectedTimeslot(e.target.value)}
            disabled={!currentSessionId}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 disabled:opacity-50 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">🟢 Live hiện tại</option>
            {timeslots.map((t) => (
              <option key={t.archived_at} value={t.archived_at}>
                📁 {new Date(t.archived_at).toLocaleString("vi-VN")} ({t.item_count} SP)
              </option>
            ))}
          </select>
        </div>

        <div className="h-6 w-px bg-slate-200" />

        {/* Mapping Mode */}
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
            </svg>
            Mapping Mode
          </label>
          <select
            value={mappingMode}
            onChange={(e) => setMappingMode(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="dl_live">📋 + 📡 DL + Live</option>
            <option value="dl_only">📋 DL Only</option>
            <option value="live_only">📡 Live Only</option>
          </select>
        </div>
      </div>

      {/* Stats Grid - 5 cards matching original */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard
          label="Có link / Tổng SP"
          value={`${withLink} / ${totalProducts}`}
          icon={Link2}
          color="purple"
        />
        <StatCard
          label="Tổng GMV"
          value={formatCurrency(totalRevenue)}
          icon={DollarSign}
          color="green"
        />
        <StatCard
          label="Tổng NMV"
          value={formatCurrency(totalNmv)}
          icon={TrendingUp}
          color="green"
        />
        <StatCard
          label="Gap (GMV - NMV)"
          value={formatCurrency(gap)}
          icon={TrendingDown}
          color="yellow"
        />
        <StatCard
          label="Top #1 GMV"
          value={formatCurrency(topGmv)}
          icon={Star}
          color="yellow"
        />
      </div>

      {/* Pinned Products */}
      {isLive && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-red-800">📌 Sản phẩm đang ghim</span>
              <span className="rounded-full bg-red-500 px-2 py-0.5 text-[10px] font-bold text-white animate-pulse">
                🔴 LIVE
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-red-400">Tự làm mới sau 30s</span>
              <button
                onClick={() => {
                  showToast("Đang làm mới dữ liệu ghim...", "info");
                }}
                className="inline-flex items-center gap-1 rounded-lg border border-red-300 bg-white px-3 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-50"
                disabled={!currentSessionId}
              >
                <RefreshCw className="h-3 w-3" />
                Làm mới
              </button>
            </div>
          </div>
          <div className="mt-3 text-sm text-red-600">
            {!currentSessionId ? (
              "⚠️ Vui lòng chọn phiên live để xem sản phẩm ghim"
            ) : (
              "⭐ Chưa có sản phẩm nào đang ghim cho phiên này"
            )}
          </div>
        </div>
      )}

      {/* Overview Metrics (live stream metrics) */}
      {currentSessionId && isLive && <OverviewMetrics sessionId={currentSessionId} />}

      {/* Charts */}
      {products.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <RevenueChart products={products} />
          <CategoryChart products={products} />
        </div>
      )}

      {/* Product Table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Spinner size="lg" />
        </div>
      ) : (
        <ProductTable products={products} shopInfo={(data as SessionDataResponse)?.shop_info} />
      )}
    </div>
  );
}
