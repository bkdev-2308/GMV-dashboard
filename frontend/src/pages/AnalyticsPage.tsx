import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/services/api";
import { formatCurrency } from "@/utils/format";
import { Upload, Search, Loader2 } from "lucide-react";

interface SheetName {
  name: string;
}

interface ItemAnalytics {
  item_name: string;
  item_id: string;
  total_revenue: number;
  sessions: {
    session_title: string;
    clicks: number;
    click_to_product_rate: number;
    orders: number;
    items_sold: number;
    revenue: number;
    click_to_order_rate: number;
    atc: number;
  }[];
}

export function AnalyticsPage() {
  // Import section state
  const [sheetUrl, setSheetUrl] = useState("");
  const [sheets, setSheets] = useState<SheetName[]>([]);
  const [selectedSheet, setSelectedSheet] = useState("");
  const [importStatus, setImportStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Search section state
  const [itemId, setItemId] = useState("");
  const [analytics, setAnalytics] = useState<ItemAnalytics | null>(null);

  const loadSheetsMutation = useMutation({
    mutationFn: () => api.post<{ success: boolean; sheets: SheetName[] }>("/api/get-sheet-names", { url: sheetUrl }),
    onSuccess: (data) => {
      if (data.success) setSheets(data.sheets);
    },
  });

  const importMutation = useMutation({
    mutationFn: () =>
      api.post<{ success: boolean; message: string }>("/api/sync-raw-monthly", {
        url: sheetUrl,
        sheet_name: selectedSheet,
      }),
    onSuccess: (data) => {
      setImportStatus({ type: data.success ? "success" : "error", message: data.message });
    },
    onError: () => {
      setImportStatus({ type: "error", message: "Lỗi kết nối" });
    },
  });

  const searchMutation = useMutation({
    mutationFn: (id: string) => api.get<{ success: boolean; data: ItemAnalytics }>(`/api/item-analytics/${id}`),
    onSuccess: (data) => {
      if (data.success) setAnalytics(data.data);
      else setAnalytics(null);
    },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (itemId.trim()) searchMutation.mutate(itemId.trim());
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Analytics</h1>

      {/* Import Section */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-800">
          <Upload className="h-5 w-5 text-purple-600" />
          Import từ Google Sheets
        </h2>

        <div className="space-y-4">
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Google Sheet URL..."
              value={sheetUrl}
              onChange={(e) => setSheetUrl(e.target.value)}
              className="flex-1 rounded-lg border border-slate-200 px-4 py-2 text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
            <button
              onClick={() => loadSheetsMutation.mutate()}
              disabled={!sheetUrl || loadSheetsMutation.isPending}
              className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-purple-700 disabled:opacity-50"
            >
              {loadSheetsMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Load Sheets"}
            </button>
          </div>

          {sheets.length > 0 && (
            <div className="flex gap-3">
              <select
                value={selectedSheet}
                onChange={(e) => setSelectedSheet(e.target.value)}
                className="flex-1 rounded-lg border border-slate-200 px-4 py-2 text-sm focus:border-blue-400 focus:outline-none"
              >
                <option value="">Chọn sheet...</option>
                {sheets.map((s) => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
              <button
                onClick={() => importMutation.mutate()}
                disabled={!selectedSheet || importMutation.isPending}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:opacity-50"
              >
                {importMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Import"}
              </button>
            </div>
          )}

          {importStatus && (
            <div className={`rounded-lg px-4 py-3 text-sm ${importStatus.type === "success" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
              {importStatus.message}
            </div>
          )}
        </div>
      </div>

      {/* Search Section */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-800">
          <Search className="h-5 w-5 text-blue-600" />
          Tra cứu sản phẩm
        </h2>

        <form onSubmit={handleSearch} className="mb-6 flex gap-3">
          <input
            type="text"
            placeholder="Nhập Item ID..."
            value={itemId}
            onChange={(e) => setItemId(e.target.value)}
            className="flex-1 rounded-lg border border-slate-200 px-4 py-2 text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          <button
            type="submit"
            disabled={searchMutation.isPending}
            className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            {searchMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Tìm kiếm"}
          </button>
        </form>

        {analytics && (
          <div className="space-y-4">
            {/* Product Info */}
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="font-semibold text-slate-800">{analytics.item_name}</p>
              <p className="text-sm text-slate-500">ID: {analytics.item_id}</p>
              <p className="mt-2 text-lg font-bold text-blue-600">
                Tổng doanh thu: {formatCurrency(analytics.total_revenue)}
              </p>
            </div>

            {/* Sessions Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    <th className="px-4 py-3 text-left font-medium text-slate-500">Session</th>
                    <th className="px-4 py-3 text-right font-medium text-slate-500">Clicks</th>
                    <th className="px-4 py-3 text-right font-medium text-slate-500">Orders</th>
                    <th className="px-4 py-3 text-right font-medium text-slate-500">Items Sold</th>
                    <th className="px-4 py-3 text-right font-medium text-slate-500">Revenue</th>
                    <th className="px-4 py-3 text-right font-medium text-slate-500">ATC</th>
                  </tr>
                </thead>
                <tbody>
                  {analytics.sessions.map((s, i) => (
                    <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="px-4 py-3 font-medium text-slate-700">{s.session_title}</td>
                      <td className="px-4 py-3 text-right text-slate-600">{s.clicks.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right text-slate-600">{s.orders.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right text-slate-600">{s.items_sold.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right font-medium text-blue-600">{formatCurrency(s.revenue)}</td>
                      <td className="px-4 py-3 text-right text-slate-600">{s.atc.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {searchMutation.isSuccess && !analytics && (
          <div className="py-8 text-center text-sm text-slate-400">Không tìm thấy sản phẩm</div>
        )}
      </div>
    </div>
  );
}
