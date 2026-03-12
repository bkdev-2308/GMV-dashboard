import { useState, useMemo, useCallback } from "react";
import { RankBadge } from "@/components/ui/RankBadge";
import { formatCurrency } from "@/utils/format";
import { useToastStore } from "@/store/toast.store";
import type { GmvProduct, SortConfig } from "@/types";
import { ArrowUpDown, ArrowUp, ArrowDown, Search, Copy, Link2 } from "lucide-react";

const SHOPEE_CDN = "https://mms.img.susercontent.com/";
const getImageUrl = (coverImage: string) =>
  coverImage.startsWith("http") ? coverImage : `${SHOPEE_CDN}${coverImage}`;

interface ShopInfo {
  shop_id: string;
  brand_name: string;
}

interface ProductTableProps {
  products: GmvProduct[];
  shopInfo?: ShopInfo[];
}

export function ProductTable({ products, shopInfo }: ProductTableProps) {
  const [sortConfig, setSortConfig] = useState<SortConfig>({ key: "revenue", direction: "desc" });
  const [searchQuery, setSearchQuery] = useState("");
  const [shopFilter, setShopFilter] = useState("");
  const [linkFilter, setLinkFilter] = useState<"all" | "with-link" | "no-link">("all");
  const [hoveredImage, setHoveredImage] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const showToast = useToastStore((s) => s.showToast);

  const handleSort = (key: SortConfig["key"]) => {
    setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === "desc" ? "asc" : "desc",
    }));
    setCurrentPage(1);
  };

  // Extract shop_id from "brand - shop_id" format
  const extractShopId = useCallback((value: string) => {
    if (value.includes(" - ")) return value.split(" - ").pop() || "";
    return value;
  }, []);

  const filteredAndSorted = useMemo(() => {
    let result = [...products];

    // Search filter
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (p) =>
          p.item_name.toLowerCase().includes(q) ||
          (p.shop_id || "").toLowerCase().includes(q)
      );
    }

    // Shop ID filter
    if (shopFilter) {
      const sid = extractShopId(shopFilter);
      result = result.filter((p) => p.shop_id === sid);
    }

    // Link filter
    if (linkFilter === "with-link") {
      result = result.filter((p) => p.link_sp);
    } else if (linkFilter === "no-link") {
      result = result.filter((p) => !p.link_sp);
    }

    // Sort
    result.sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortConfig.direction === "asc" ? aVal - bVal : bVal - aVal;
      }
      const aStr = String(aVal ?? "");
      const bStr = String(bVal ?? "");
      return sortConfig.direction === "asc"
        ? aStr.localeCompare(bStr)
        : bStr.localeCompare(aStr);
    });

    return result;
  }, [products, searchQuery, shopFilter, linkFilter, sortConfig, extractShopId]);

  // Pagination
  const totalPages = Math.ceil(filteredAndSorted.length / perPage);
  const paginatedData = filteredAndSorted.slice((currentPage - 1) * perPage, currentPage * perPage);

  const SortIcon = ({ columnKey }: { columnKey: SortConfig["key"] }) => {
    if (sortConfig.key !== columnKey) return <ArrowUpDown className="h-3 w-3 opacity-40" />;
    return sortConfig.direction === "asc" ? (
      <ArrowUp className="h-3 w-3" />
    ) : (
      <ArrowDown className="h-3 w-3" />
    );
  };

  const copyLink = async (link: string) => {
    try {
      await navigator.clipboard.writeText(link);
      showToast("Đã copy link!", "success");
    } catch {
      // silent
    }
  };

  const bulkCopyLinks = async (count: number) => {
    const links = filteredAndSorted
      .filter((p) => p.link_sp)
      .slice(0, count)
      .map((p) => p.link_sp);
    if (links.length === 0) {
      showToast("Không có link để copy", "error");
      return;
    }
    try {
      await navigator.clipboard.writeText(links.join("\n"));
      showToast(`Đã copy ${links.length} links!`, "success");
    } catch {
      // silent
    }
  };

  const columns: { key: keyof GmvProduct; label: string }[] = [
    { key: "revenue", label: "GMV" },
    { key: "clicks", label: "CLICKS" },
    { key: "add_to_cart", label: "ATC" },
    { key: "orders", label: "ĐƠN HÀNG" },
    { key: "items_sold", label: "ĐÃ BÁN" },
    { key: "confirmed_revenue", label: "NMV" },
    { key: "gia_live", label: "GIÁ LIVE" },
    { key: "giam_stock", label: "GIẢM STOCK" },
  ];

  // Build shop suggestions for datalist
  const shopSuggestions = useMemo(() => {
    if (shopInfo && shopInfo.length > 0) {
      return shopInfo.slice(0, 20).map((s) =>
        s.brand_name ? `${s.brand_name} - ${s.shop_id}` : s.shop_id
      );
    }
    // Fallback: unique shop IDs from products
    const ids = [...new Set(products.map((p) => p.shop_id).filter(Boolean))];
    return ids.slice(0, 20);
  }, [shopInfo, products]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      {/* Table Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-800">Top Sản phẩm</h3>
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-500">
            {filteredAndSorted.length} sản phẩm
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Bulk copy */}
          <div className="flex items-center gap-1">
            <select
              className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-600"
              id="bulkCopyCount"
              defaultValue="50"
            >
              <option value="50">Top 50</option>
              <option value="100">Top 100</option>
              <option value="200">Top 200</option>
              <option value="500">Top 500</option>
            </select>
            <button
              onClick={() => {
                const count = parseInt(
                  (document.getElementById("bulkCopyCount") as HTMLSelectElement)?.value || "50"
                );
                bulkCopyLinks(count);
              }}
              className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
            >
              <Copy className="h-3 w-3" />
              Copy Links
            </button>
          </div>

          {/* Link filter */}
          <select
            value={linkFilter}
            onChange={(e) => {
              setLinkFilter(e.target.value as typeof linkFilter);
              setCurrentPage(1);
            }}
            className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-600"
          >
            <option value="all">📦 Tất cả</option>
            <option value="with-link">✅ Có link</option>
            <option value="no-link">❌ Không link</option>
          </select>

          {/* Shop ID filter */}
          <div className="relative">
            <input
              type="text"
              list="shopIdList"
              placeholder="🔍 Shop ID..."
              value={shopFilter}
              onChange={(e) => {
                setShopFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-36 rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-600 focus:border-blue-400 focus:outline-none"
            />
            <datalist id="shopIdList">
              {shopSuggestions.map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Tìm sản phẩm..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              className="w-44 rounded-md border border-slate-200 bg-slate-50 py-1.5 pl-7 pr-3 text-xs focus:border-blue-400 focus:bg-white focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              <th className="px-4 py-3 text-left font-medium text-slate-500">#</th>
              <th className="px-4 py-3 text-left font-medium text-slate-500">Sản phẩm</th>
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  className="cursor-pointer px-4 py-3 text-right font-medium text-slate-500 hover:text-slate-700"
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    <SortIcon columnKey={col.key} />
                  </span>
                </th>
              ))}
              <th className="px-4 py-3 text-center font-medium text-slate-500">Link</th>
            </tr>
          </thead>
          <tbody>
            {paginatedData.map((product, index) => {
              const globalIndex = (currentPage - 1) * perPage + index;
              return (
                <tr
                  key={product.item_id}
                  className="border-b border-slate-100 transition-colors hover:bg-slate-50"
                >
                  <td className="px-4 py-3">
                    <RankBadge rank={globalIndex + 1} />
                  </td>
                  <td className="max-w-[280px] px-4 py-3">
                    <div className="flex items-center gap-3">
                      {product.cover_image && (
                        <div
                          className="relative"
                          onMouseEnter={() => setHoveredImage(product.item_id)}
                          onMouseLeave={() => setHoveredImage(null)}
                        >
                          <img
                            src={getImageUrl(product.cover_image)}
                            alt=""
                            className="h-10 w-10 rounded-lg border border-slate-200 object-cover"
                            loading="lazy"
                          />
                          {hoveredImage === product.item_id && (
                            <div className="fixed left-1/2 top-1/2 z-[10000] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-xl border-2 border-slate-200 bg-white p-2 shadow-2xl">
                              <img
                                src={getImageUrl(product.cover_image)}
                                alt={product.item_name}
                                className="h-[300px] w-[300px] object-contain"
                              />
                            </div>
                          )}
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-slate-800" title={product.item_name}>
                          {product.item_name}
                        </span>
                        {product.shop_id && (
                          <span className="text-xs text-slate-400">{product.shop_id}</span>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-blue-600">
                    {formatCurrency(product.revenue)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600">
                    {(product.clicks || 0).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600">
                    {(product.add_to_cart || 0).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600">
                    {(product.orders || 0).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600">
                    {(product.items_sold || 0).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-emerald-600">
                    {formatCurrency(product.confirmed_revenue)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-500">
                    {product.gia_live ? formatCurrency(product.gia_live) : <span className="text-slate-300">-</span>}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-500">
                    {product.giam_stock ? formatCurrency(product.giam_stock) : <span className="text-slate-300">-</span>}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {product.link_sp ? (
                      <button
                        onClick={() => copyLink(product.link_sp)}
                        className="rounded-md p-1.5 text-emerald-500 transition-colors hover:bg-emerald-50"
                        title="Copy link"
                      >
                        <Link2 className="h-4 w-4" />
                      </button>
                    ) : (
                      <span className="text-xs text-slate-300">-</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {paginatedData.length === 0 && (
          <div className="py-12 text-center text-sm text-slate-400">
            Không tìm thấy sản phẩm
          </div>
        )}
      </div>

      {/* Pagination */}
      {filteredAndSorted.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-4 py-3">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span>Hiển thị:</span>
            <select
              value={perPage}
              onChange={(e) => {
                setPerPage(Number(e.target.value));
                setCurrentPage(1);
              }}
              className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs"
            >
              <option value="10">10</option>
              <option value="20">20</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
            <span>/trang</span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="rounded-md border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-40"
            >
              ←
            </button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let page: number;
              if (totalPages <= 7) {
                page = i + 1;
              } else if (currentPage <= 4) {
                page = i + 1;
              } else if (currentPage >= totalPages - 3) {
                page = totalPages - 6 + i;
              } else {
                page = currentPage - 3 + i;
              }
              return (
                <button
                  key={page}
                  onClick={() => setCurrentPage(page)}
                  className={`rounded-md px-2.5 py-1 text-xs ${currentPage === page
                      ? "bg-blue-600 text-white"
                      : "border border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                >
                  {page}
                </button>
              );
            })}
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="rounded-md border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-40"
            >
              →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
