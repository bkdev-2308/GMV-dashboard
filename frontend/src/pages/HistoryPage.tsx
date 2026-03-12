import { useState, useEffect, useRef, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { sessionService } from "@/services/session.service";
import { formatCurrency } from "@/utils/format";
import { RankBadge } from "@/components/ui/RankBadge";
import { Spinner } from "@/components/ui/Spinner";
import { Search, Package, DollarSign, TrendingUp, TrendingDown, Download } from "lucide-react";

export function HistoryPage() {
  const [selectedSession, setSelectedSession] = useState("");
  const [selectedTimeslot, setSelectedTimeslot] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [sessionSearch, setSessionSearch] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const { data: sessionsData } = useQuery({
    queryKey: ["archived-sessions"],
    queryFn: sessionService.getArchivedSessions,
  });

  const { data: timeslotsData } = useQuery({
    queryKey: ["history-timeslots", selectedSession],
    queryFn: () => sessionService.getTimeslots(selectedSession),
    enabled: !!selectedSession,
  });

  const { data: historyData, isLoading } = useQuery({
    queryKey: ["history-data", selectedSession, selectedTimeslot],
    queryFn: () => sessionService.getHistoryData(selectedSession, selectedTimeslot),
    enabled: !!selectedSession && !!selectedTimeslot,
  });

  const sessions = sessionsData?.success ? sessionsData.sessions : [];
  const timeslots = timeslotsData?.success ? timeslotsData.timeslots : [];
  const products = historyData?.success ? historyData.data : [];
  const stats = historyData?.success ? historyData.stats : null;

  const filteredSessions = sessions.filter((s) =>
    (s.session_title || "").toLowerCase().includes(sessionSearch.toLowerCase())
  );

  const selectedTitle = useMemo(() => {
    const s = sessions.find((s) => s.session_id === selectedSession);
    if (!s) return "";
    return `${s.session_title} (${s.item_count} SP, ${s.timeslot_count} khung giờ)`;
  }, [sessions, selectedSession]);

  const filteredProducts = useMemo(() => {
    if (!searchQuery) return products;
    const q = searchQuery.toLowerCase();
    return products.filter(
      (p) => p.item_name.toLowerCase().includes(q) || (p.shop_id || "").toLowerCase().includes(q)
    );
  }, [products, searchQuery]);

  // Compute gap percent like the template
  const gapPercent = stats && stats.total_gmv > 0
    ? ((stats.gap / stats.total_gmv) * 100).toFixed(1)
    : "0";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Lịch sử Phiên</h1>

      {/* Filter Card */}
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-slate-200 bg-white px-5 py-3">
        <div className="flex flex-col gap-1.5">
          <label className="flex items-center gap-1.5 text-xs font-semibold text-slate-500">
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="7" width="20" height="15" rx="2" ry="2" />
              <polyline points="17 2 12 7 7 2" />
            </svg>
            Phiên đã archive
          </label>
          <div ref={dropdownRef} className="relative min-w-[350px]">
            <input
              type="text"
              placeholder="Gõ để tìm hoặc click chọn phiên..."
              value={dropdownOpen ? sessionSearch : selectedTitle}
              onClick={() => {
                setDropdownOpen(true);
                setSessionSearch("");
              }}
              onChange={(e) => {
                setSessionSearch(e.target.value);
                if (!dropdownOpen) setDropdownOpen(true);
              }}
              className="w-full rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
              autoComplete="off"
            />
            {dropdownOpen && (
              <div className="absolute left-0 top-full z-20 mt-1 max-h-[300px] w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
                {filteredSessions.length > 0 ? (
                  filteredSessions.map((s) => (
                    <button
                      key={s.session_id}
                      onClick={() => {
                        setSelectedSession(s.session_id);
                        setSelectedTimeslot("");
                        setDropdownOpen(false);
                        setSessionSearch("");
                      }}
                      className="w-full border-b border-slate-100 px-4 py-3 text-left text-sm text-slate-700 last:border-b-0 hover:bg-slate-50"
                    >
                      {s.session_title} ({s.item_count} SP, {s.timeslot_count} khung giờ)
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-3 text-sm text-slate-400">Không tìm thấy phiên</div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="h-10 w-px bg-slate-200" />

        <div className="flex flex-col gap-1.5">
          <label className="flex items-center gap-1.5 text-xs font-semibold text-slate-500">
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            Khung giờ
          </label>
          <select
            value={selectedTimeslot}
            onChange={(e) => setSelectedTimeslot(e.target.value)}
            disabled={!selectedSession}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">-- Chọn khung giờ --</option>
            {timeslots.map((t) => {
              const dt = new Date(t.archived_at);
              const label =
                dt.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }) +
                " " +
                dt.toLocaleDateString("vi-VN") +
                ` (${t.item_count} SP)`;
              return (
                <option key={t.archived_at} value={t.archived_at}>
                  {label}
                </option>
              );
            })}
          </select>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Spinner size="lg" />
        </div>
      )}

      {/* Stats Summary */}
      {stats && !isLoading && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                <Package className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500">Tổng sản phẩm</p>
                <p className="text-2xl font-bold text-slate-900">{historyData?.count || 0}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                <DollarSign className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500">Tổng GMV</p>
                <p className="text-2xl font-bold text-slate-900">{formatCurrency(stats.total_gmv)}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
                <TrendingUp className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500">Tổng NMV</p>
                <p className="text-2xl font-bold text-slate-900">{formatCurrency(stats.total_nmv)}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                <TrendingDown className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500">Gap (GMV - NMV)</p>
                <p className="text-2xl font-bold text-slate-900">
                  {formatCurrency(stats.gap)} ({gapPercent}%)
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Search + Table */}
      {products.length > 0 && !isLoading && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="flex items-center justify-between gap-3 border-b border-slate-200 p-4">
            <div className="relative max-w-sm flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Tìm sản phẩm..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm focus:border-blue-400 focus:bg-white focus:outline-none"
              />
            </div>
            <button
              onClick={() => {
                const params = new URLSearchParams();
                if (selectedSession) params.set("session_id", selectedSession);
                if (selectedTimeslot) params.set("archived_at", selectedTimeslot);
                window.location.href = `/api/history/export?${params}`;
              }}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <Download className="h-4 w-4" />
              Export CSV
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-4 py-3 text-left font-semibold text-slate-500">STT</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-500">Tên sản phẩm</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-500">GMV</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-500">NMV</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-500">Clicks</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-500">ATC</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-500">Đơn hàng</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.map((p, i) => (
                  <tr key={p.item_id} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-3"><RankBadge rank={i + 1} /></td>
                    <td className="max-w-[250px] px-4 py-3">
                      <span className="block truncate font-medium text-slate-800" title={p.item_name}>
                        {p.item_name || "N/A"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-blue-600">{formatCurrency(p.revenue)}</td>
                    <td className="px-4 py-3 text-right font-medium text-emerald-600">{formatCurrency(p.confirmed_revenue)}</td>
                    <td className="px-4 py-3 text-right text-slate-600">{(p.clicks || 0).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-slate-600">{(p.add_to_cart || 0).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-slate-600">{(p.orders || 0).toLocaleString()}</td>
                  </tr>
                ))}
                {filteredProducts.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-sm text-slate-400">
                      Không có dữ liệu
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!selectedSession && !isLoading && (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
          Chọn phiên và khung giờ để xem dữ liệu lịch sử
        </div>
      )}

      {selectedSession && !selectedTimeslot && !isLoading && (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
          Chọn khung giờ để xem dữ liệu
        </div>
      )}
    </div>
  );
}
