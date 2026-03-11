// Session types
export interface Session {
  session_id: string;
  session_title: string;
  item_count: number;
  last_scraped: string | null;
}

// Archived session (from history)
export interface ArchivedSession {
  session_id: string;
  session_title: string;
  item_count: number;
  timeslot_count: number;
  last_archived: string | null;
}

// Timeslot for history
export interface Timeslot {
  archived_at: string;
  item_count: number;
}

// GMV product data row - matches backend field names
export interface GmvProduct {
  item_id: string;
  item_name: string;
  shop_id: string;
  cover_image: string;
  link_sp: string;
  revenue: number;
  confirmed_revenue: number;
  clicks: number;
  ctr: number;
  orders: number;
  items_sold: number;
  add_to_cart: number;
  cluster: string;
  datetime: string;
  session_id?: string;
  session_title?: string;
}

// Dashboard stats from /api/all-data
export interface DashboardStats {
  total_products: number;
  total_revenue: number;
  total_confirmed_revenue: number;
  total_clicks: number;
  total_orders: number;
  total_items_sold: number;
  with_link: number;
}

// History stats from /api/history/data
export interface HistoryStats {
  total_gmv: number;
  total_nmv: number;
  gap: number;
}

// API response wrapper
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
}

// Session data response from /api/all-data
export interface SessionDataResponse {
  success: boolean;
  data: GmvProduct[];
  stats: DashboardStats;
  shop_ids: string[];
  shop_info: { shop_id: string; brand_name: string }[];
  last_sync: string | null;
  from_cache: boolean;
}

// History data response from /api/history/data
export interface HistoryDataResponse {
  success: boolean;
  data: GmvProduct[];
  stats: HistoryStats;
  count: number;
  session_id: string;
  archived_at: string;
}

// Sessions list response
export interface SessionsResponse {
  success: boolean;
  sessions: Session[];
  count: number;
}

// Archived sessions response
export interface ArchivedSessionsResponse {
  success: boolean;
  sessions: ArchivedSession[];
  count: number;
}

// Timeslots response
export interface TimeslotsResponse {
  success: boolean;
  timeslots: Timeslot[];
  count: number;
  session_id: string;
}

// User from /api/me
export interface User {
  id: number;
  email: string;
  name: string;
  role: string;
  picture?: string;
}

// /api/me response
export interface MeResponse {
  success: boolean;
  user?: User;
  is_admin: boolean;
  can_access_settings?: boolean;
  error?: string;
}

// Brand user
export interface BrandUser {
  id: number;
  email: string;
  full_name: string;
  shop_ids: string[];
  brand_label: string;
}

// Admin user
export interface AdminUser {
  id: number;
  email: string;
  name: string;
  role: string;
  last_login: string | null;
}

// Host performance
export interface HostPerformance {
  host_name: string;
  total_sessions: number;
  total_duration_minutes: number;
  total_gmv: number;
  total_nmv: number;
  avg_gmv_per_hour: number;
}

// Sort direction
export type SortDirection = "asc" | "desc";

// Sort config
export interface SortConfig {
  key: keyof GmvProduct;
  direction: SortDirection;
}
