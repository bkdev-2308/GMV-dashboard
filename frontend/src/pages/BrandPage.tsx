import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { authService } from "@/services/auth.service";
import { formatCurrency } from "@/utils/format";
import { Spinner } from "@/components/ui/Spinner";
import { Search, DollarSign, Package, Store, TrendingUp, ArrowUpDown, ArrowUp, ArrowDown, LogOut } from "lucide-react";

const SHOPEE_CDN = "https://mms.img.susercontent.com/";
const getImageUrl = (img: string) => img.startsWith("http") ? img : `${SHOPEE_CDN}${img}`;

interface BrandProduct {
  item_id: string;
  item_name: string;
  shop_id: string;
  revenue: number;
  confirmed_revenue: number;
  clicks: number;
  orders: number;
  add_to_cart: number;
}

interface BrandStats {
  total_products: number;
  total_gmv: number;
  total_nmv: number;
  total_shops: number;
}

type SortKey = "revenue" | "confirmed_revenue" | "clicks" | "orders" | "add_to_cart";

export function BrandPage() {
  const [sortKey, setSortKey] = useState<SortKey>("revenue");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [searchQuery, setSearchQuery] = useState("");
  const [sessionFilter, setSessionFilter] = useState("");
  const [hoveredImage, setHoveredImage] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["brand-data", sessionFilter],
    queryFn: () => {
      const url = sessionFilter ? `/api/brand/gmv-data?session_id=${sessionFilter}` : "/api/brand/gmv-data";
      return api.get<{ success: boolean; data: BrandProduct[]; stats: BrandStats }>(url);
    },
  });

  const { data: sessionsData } = useQuery({
    queryKey: ["brand-sessions"],
    queryFn: () => api.get<{ success: boolean; sessions: { session_id: string; session_title: string }[] }>("/api/sessions"),
  });
  const sessions = sessionsData?.success ? sessionsData.sessions : [];

  const products = data?.success ? data.data : [];
  const stats = data?.success ? data.stats : null;

  const sorted = useMemo(() => {
    let filtered = [...products];
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(p => p.item_name.toLowerCase().includes(q) || p.shop_id.toLowerCase().includes(q));
    }
    return filtered.sort((a, b) => {
      const aVal = a[sortKey] as number;
      const bVal = b[sortKey] as number;
      return sortDir === "asc" ? aVal - bVal : bVal - aVal;
    });
  }, [products, sortKey, sortDir, searchQuery]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (sortKey !== k) return <ArrowUpDown className="h-3 w-3 opacity-40" />;
    return sortDir === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />;
  };

  const columnLabels: Record<SortKey, string> = {
    revenue: "GMV",
    clicks: "CLICKS",
    orders: "ORDERS",
    add_to_cart: "ATC",
    confirmed_revenue: "NMV",
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 p-6 text-white">
        <div>
          <h1 className="text-2xl font-bold">Brand Portal</h1>
          <p className="mt-1 text-sm text-white/80">{stats?.total_shops || 0} shop được gán</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={sessionFilter}
            onChange={(e) => setSessionFilter(e.target.value)}
            className="rounded-lg bg-white/20 px-3 py-1.5 text-sm text-white focus:outline-none"
          >
            <option value="">Tất cả phiên</option>
            {sessions.map(s => (
              <option key={s.session_id} value={s.session_id}>{s.session_title || s.session_id}</option>
            ))}
          </select>
          <button
            onClick={() => authService.brandLogout()}
            className="flex items-center gap-2 rounded-lg bg-white/20 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-white/30"
          >
            <LogOut className="h-4 w-4" />
            Đăng xuất
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600"><DollarSign className="h-5 w-5" /></div>
              <div>
                <p className="text-xs font-medium text-slate-500">Tổng GMV</p>
                <p className="text-lg font-bold text-slate-900">{formatCurrency(stats.total_gmv)}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600"><TrendingUp className="h-5 w-5" /></div>
              <div>
                <p className="text-xs font-medium text-slate-500">Tổng NMV</p>
                <p className="text-lg font-bold text-slate-900">{formatCurrency(stats.total_nmv)}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50 text-purple-600"><Package className="h-5 w-5" /></div>
              <div>
                <p className="text-xs font-medium text-slate-500">Sản phẩm</p>
                <p className="text-lg font-bold text-slate-900">{stats.total_products}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-600"><Store className="h-5 w-5" /></div>
              <div>
                <p className="text-xs font-medium text-slate-500">Shops</p>
                <p className="text-lg font-bold text-slate-900">{stats.total_shops}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="Tìm sản phẩm hoặc shop..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-4 text-sm focus:border-blue-400 focus:outline-none"
        />
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-4 py-3 text-left font-medium text-slate-500">Sản phẩm</th>
                <th className="px-4 py-3 text-left font-medium text-slate-500">Shop</th>
                {(["revenue", "clicks", "orders", "add_to_cart", "confirmed_revenue"] as SortKey[]).map((k) => (
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
                  <td className="max-w-[200px] px-4 py-3">
                    <div className="flex items-center gap-3">
                      {(p as BrandProduct & { cover_image?: string }).cover_image && (
                        <div
                          className="relative"
                          onMouseEnter={() => setHoveredImage(p.item_id)}
                          onMouseLeave={() => setHoveredImage(null)}
                        >
                          <img
                            src={getImageUrl((p as BrandProduct & { cover_image?: string }).cover_image!)}
                            alt=""
                            className="h-9 w-9 rounded-lg border border-slate-200 object-cover"
                            loading="lazy"
                          />
                          {hoveredImage === p.item_id && (
                            <div className="absolute left-10 top-0 z-30 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
                              <img src={getImageUrl((p as BrandProduct & { cover_image?: string }).cover_image!)} alt={p.item_name} className="h-[180px] w-[180px] object-cover" />
                            </div>
                          )}
                        </div>
                      )}
                      <span className="truncate font-medium text-slate-800" title={p.item_name}>{p.item_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{p.shop_id}</span>
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-blue-600">{formatCurrency(p.revenue)}</td>
                  <td className="px-4 py-3 text-right text-slate-600">{(p.clicks || 0).toLocaleString()}</td>
                  <td className="px-4 py-3 text-right text-slate-600">{(p.orders || 0).toLocaleString()}</td>
                  <td className="px-4 py-3 text-right text-slate-600">{(p.add_to_cart || 0).toLocaleString()}</td>
                  <td className="px-4 py-3 text-right font-medium text-emerald-600">{formatCurrency(p.confirmed_revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
