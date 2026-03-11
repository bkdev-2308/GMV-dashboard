import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { formatCurrency } from "@/utils/format";
import { useToastStore } from "@/store/toast.store";
import { RankBadge } from "@/components/ui/RankBadge";
import { Spinner } from "@/components/ui/Spinner";
import { Download, Loader2, Users, RefreshCw, FileText } from "lucide-react";

interface HostPerformance {
  host_name: string;
  total_sessions: number;
  total_minutes: number;
  achieved_gmv: number;
  total_gmv: number;
  avg_views: number;
  avg_pcu: number;
  total_orders: number;
}

export function HostPerformancePage() {
  const [sheetUrl, setSheetUrl] = useState("");
  const [hostFilter, setHostFilter] = useState("");
  const [timeFilter, setTimeFilter] = useState("all");
  const showToast = useToastStore((s) => s.showToast);
  const queryClient = useQueryClient();
  const [lastSync, setLastSync] = useState<string | null>(null);

  const syncMutation = useMutation({
    mutationFn: () =>
      api.post<{ success: boolean; message: string; count?: number }>(
        "/api/host/sync-schedule",
        { sheet_url: sheetUrl },
      ),
    onSuccess: (data) => {
      if (data.success) {
        showToast(data.message || "Đồng bộ lịch thành công!", "success");
        setLastSync(`Just now (${data.count ?? 0} entries)`);
        queryClient.invalidateQueries({ queryKey: ["host-performance"] });
        queryClient.invalidateQueries({ queryKey: ["host-performance-all"] });
      } else {
        showToast(data.message || "Lỗi đồng bộ", "error");
      }
    },
    onError: () => showToast("Lỗi kết nối server", "error"),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["host-performance", hostFilter, timeFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (hostFilter) params.set("host", hostFilter);
      if (timeFilter !== "all") params.set("time", timeFilter);
      return api.get<{
        success: boolean;
        data: HostPerformance[];
        count: number;
      }>(`/api/host/performance?${params}`);
    },
  });

  const performances = data?.success ? data.data ?? [] : [];

  // Extract unique host names from all performance data (unfiltered query)
  const { data: allData } = useQuery({
    queryKey: ["host-performance-all"],
    queryFn: () =>
      api.get<{ success: boolean; data: HostPerformance[] }>("/api/host/performance"),
  });
  const hosts = useMemo(() => {
    const list = allData?.success ? allData.data ?? [] : [];
    return [...new Set(list.map((p) => p.host_name))].sort();
  }, [allData]);

  const handleExport = () => {
    const params = new URLSearchParams();
    if (hostFilter) params.set("host", hostFilter);
    if (timeFilter !== "all") params.set("time", timeFilter);
    window.location.href = `/api/host/export?${params}`;
    showToast("Downloading CSV...", "success");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Host Performance Report
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Đánh giá hiệu suất host &amp; co-host từ dữ liệu livestream
          </p>
        </div>
      </header>

      {/* Lịch Host Schedule Section */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h3 className="mb-4 flex items-center gap-2 text-base font-semibold text-slate-800">
          <FileText className="h-5 w-5 text-slate-600" />
          Lịch Host Schedule
        </h3>

        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[300px] flex-1">
            <label className="mb-1.5 block text-xs font-medium text-slate-500">
              Sheet URL:
            </label>
            <input
              type="text"
              placeholder="https://docs.google.com/spreadsheets/d/..."
              value={sheetUrl}
              onChange={(e) => setSheetUrl(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-4 py-2.5 text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <button
            onClick={() => syncMutation.mutate()}
            disabled={!sheetUrl || syncMutation.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            {syncMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Load từ Sheet
          </button>
        </div>

        {lastSync && (
          <div className="mt-3 inline-flex items-center gap-2 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <span>Last sync: {lastSync}</span>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-slate-200 bg-white px-5 py-3">
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
            <Users className="h-3.5 w-3.5" />
            Host
          </label>
          <select
            value={hostFilter}
            onChange={(e) => setHostFilter(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">All Hosts</option>
            {hosts.map((h) => (
              <option key={h} value={h}>
                {h}
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
            Thời gian
          </label>
          <select
            value={timeFilter}
            onChange={(e) => setTimeFilter(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="all">All time</option>
            <option value="7days">Last 7 days</option>
            <option value="30days">Last 30 days</option>
          </select>
        </div>
      </div>

      {/* Host Ranking Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <h3 className="text-lg font-semibold text-slate-800">Host Ranking</h3>
          <button
            onClick={handleExport}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
          >
            <Download className="h-4 w-4" />
            Export CSV
          </button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Spinner size="lg" />
          </div>
        ) : performances.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gradient-to-r from-slate-800 to-slate-900 text-white">
                  <th className="border-r border-white/10 px-4 py-3.5 text-left text-xs font-bold uppercase tracking-wider">Rank</th>
                  <th className="border-r border-white/10 px-4 py-3.5 text-left text-xs font-bold uppercase tracking-wider">Host</th>
                  <th className="border-r border-white/10 px-4 py-3.5 text-right text-xs font-bold uppercase tracking-wider">Sessions</th>
                  <th className="border-r border-white/10 px-4 py-3.5 text-right text-xs font-bold uppercase tracking-wider">Hours</th>
                  <th className="border-r border-white/10 px-4 py-3.5 text-right text-xs font-bold uppercase tracking-wider">GMV Đạt Được</th>
                  <th className="border-r border-white/10 px-4 py-3.5 text-right text-xs font-bold uppercase tracking-wider">Total GMV</th>
                  <th className="border-r border-white/10 px-4 py-3.5 text-right text-xs font-bold uppercase tracking-wider">Avg Views</th>
                  <th className="border-r border-white/10 px-4 py-3.5 text-right text-xs font-bold uppercase tracking-wider">Avg PCU</th>
                  <th className="px-4 py-3.5 text-right text-xs font-bold uppercase tracking-wider">Total Orders</th>
                </tr>
              </thead>
              <tbody>
                {performances.map((p, i) => {
                  const hours = p.total_minutes ? (p.total_minutes / 60).toFixed(1) : "0";
                  return (
                    <tr
                      key={p.host_name}
                      className="border-b border-slate-200 odd:bg-slate-50/50 hover:bg-slate-100"
                    >
                      <td className="px-4 py-3">
                        <RankBadge rank={i + 1} />
                      </td>
                      <td className="px-4 py-3 font-semibold text-slate-800">
                        {p.host_name || "N/A"}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-600">
                        {(p.total_sessions || 0).toLocaleString("vi-VN")}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-600">
                        {hours}h
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-emerald-600">
                        {formatCurrency(p.achieved_gmv || 0)}
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-blue-600">
                        {formatCurrency(p.total_gmv || 0)}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-600">
                        {(p.avg_views || 0).toLocaleString("vi-VN")}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-600">
                        {(p.avg_pcu || 0).toLocaleString("vi-VN")}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-slate-800">
                        {(p.total_orders || 0).toLocaleString("vi-VN")}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-12 text-center text-sm text-slate-400">
            {data ? "Không có dữ liệu" : "Nhấn \"Load từ Sheet\" để bắt đầu"}
          </div>
        )}
      </div>
    </div>
  );
}
