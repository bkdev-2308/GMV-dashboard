import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { formatCurrency } from "@/utils/format";
import { Spinner } from "@/components/ui/Spinner";
import { Search, ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";

const SHOPEE_CDN = "https://mms.img.susercontent.com/";
const getImageUrl = (img: string) =>
  img.startsWith("http") ? img : `${SHOPEE_CDN}${img}`;

interface StaffProduct {
  item_id: string;
  item_name: string;
  cover_image: string;
  revenue: number;
  confirmed_revenue: number;
  shop_id: string;
  clicks: number;
  add_to_cart: number;
  orders: number;
  session_id: string;
}

type SortKey = "revenue" | "clicks" | "add_to_cart" | "orders" | "confirmed_revenue";

export function StaffPage() {
  const [query, setQuery] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [searchTrigger, setSearchTrigger] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("revenue");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [hoveredImage, setHoveredImage] = useState<string | null>(null);

  const { data: sessionsData } = useQuery({
    queryKey: ["staff-sessions"],
    queryFn: () => api.get<{ success: boolean; sessions: { session_id: string; session_title: string }[] }>("/api/sessions"),
  });

  const sessions = sessionsData?.success ? sessionsData.sessions : [];

  const { data: searchData, isLoading } = useQuery({
    queryKey: ["staff-search", searchTrigger, sessionId],
    queryFn: () => {
      const params = new URLSearchParams({ q: searchTrigger });
      if (sessionId) params.set("session_id", sessionId);
      return api.get<{ success: boolean; data: StaffProduct[]; count: number }>(`/api/staff/search?${params}`);
    },
    enabled: !!searchTrigger,
  });

  const results = searchData?.success ? searchData.data : [];

  const sorted = useMemo(() => {
    return [...results].sort((a, b) => {
      const aVal = a[sortKey] as number;
      const bVal = b[sortKey] as number;
      return sortDir === "asc" ? aVal - bVal : bVal - aVal;
    });
  }, [results, sortKey, sortDir]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) setSearchTrigger(query.trim());
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortKey(key); setSortDir("desc"); }
  };

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (sortKey !== k) return <ArrowUpDown className="h-3 w-3 opacity-40" />;
    return sortDir === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />;
  };

  const columnLabels: Record<SortKey, string> = {
    revenue: "GMV",
    clicks: "CLICKS",
    add_to_cart: "ATC",
    orders: "ORDERS",
    confirmed_revenue: "NMV",
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Staff Dashboard</h1>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Tìm theo Shop ID hoặc tên sản phẩm..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-9 pr-4 text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>
        <select
          value={sessionId}
          onChange={(e) => setSessionId(e.target.value)}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
        >
          <option value="">Tất cả session</option>
          {sessions.map((s) => (
            <option key={s.session_id} value={s.session_id}>{s.session_title || s.session_id}</option>
          ))}
        </select>
        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Tìm kiếm
        </button>
      </form>

      {/* Stats */}
      {results.length > 0 && (
        <div className="flex gap-4 text-sm">
          <span className="text-slate-500">{results.length} sản phẩm</span>
        </div>
      )}

      {/* Results */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>
      ) : sorted.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-4 py-3 text-left font-medium text-slate-500">Sản phẩm</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-500">Shop</th>
                  {(Object.keys(columnLabels) as SortKey[]).map((k) => (
                    <th
                      key={k}
                      onClick={() => handleSort(k)}
                      className="cursor-pointer px-4 py-3 text-right font-medium text-slate-500 hover:text-slate-700"
                    >
                      <span className="inline-flex items-center gap-1">
                        {columnLabels[k]} <SortIcon k={k} />
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((p) => (
                  <tr key={p.item_id} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="max-w-[250px] px-4 py-3">
                      <div className="flex items-center gap-3">
                        {p.cover_image && (
                          <div
                            className="relative"
                            onMouseEnter={() => setHoveredImage(p.item_id)}
                            onMouseLeave={() => setHoveredImage(null)}
                          >
                            <img src={getImageUrl(p.cover_image)} alt="" className="h-10 w-10 rounded-lg border border-slate-200 object-cover" loading="lazy" />
                            {hoveredImage === p.item_id && (
                              <div className="absolute left-12 top-0 z-30 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
                                <img src={getImageUrl(p.cover_image)} alt={p.item_name} className="h-[200px] w-[200px] object-cover" />
                              </div>
                            )}
                          </div>
                        )}
                        <a
                          href={`https://shopee.vn/product/${p.shop_id}/${p.item_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="truncate font-medium text-slate-800 hover:text-blue-600 hover:underline"
                          title={p.item_name}
                        >
                          {p.item_name}
                        </a>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{p.shop_id}</span>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-blue-600">{formatCurrency(p.revenue)}</td>
                    <td className="px-4 py-3 text-right font-medium text-emerald-600">{formatCurrency(p.confirmed_revenue)}</td>
                    <td className="px-4 py-3 text-right text-slate-600">{(p.clicks || 0).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-slate-600">{(p.add_to_cart || 0).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-slate-600">{(p.orders || 0).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : searchTrigger && !isLoading ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
          Không tìm thấy kết quả cho &ldquo;{searchTrigger}&rdquo;
        </div>
      ) : !searchTrigger ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
          Nhập Shop ID hoặc tên sản phẩm để tìm kiếm
        </div>
      ) : null}
    </div>
  );
}
