import { api } from "./api";

interface TopProductRow {
  name: string;
  revenue: number;
  clicks: number;
  add_to_cart: number;
  orders: number;
}

interface CategoryRow {
  cluster: string;
  revenue: number;
  clicks: number;
  add_to_cart: number;
  orders: number;
  count: number;
}

export const analyticsService = {
  getTopProducts: (sessionId?: string, metric = "revenue") => {
    const params = new URLSearchParams({ metric });
    if (sessionId) params.set("session_id", sessionId);
    return api.get<{ success: boolean; data: TopProductRow[] }>(
      `/api/analytics/top-products?${params}`
    );
  },

  getCategoryDistribution: (sessionId?: string, metric = "revenue") => {
    const params = new URLSearchParams({ metric });
    if (sessionId) params.set("session_id", sessionId);
    return api.get<{ success: boolean; data: CategoryRow[]; metric: string }>(
      `/api/analytics/category-distribution?${params}`
    );
  },

  getItemAnalytics: (itemId: string) =>
    api.get<{ success: boolean; data: unknown }>(`/api/item-analytics/${itemId}`),
};
