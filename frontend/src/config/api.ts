export const API_BASE = "";  // Uses Vite proxy in dev

export const API_ENDPOINTS = {
  // Sessions
  sessions: "/api/sessions",
  sessionRename: "/api/session-rename",
  sessionsCleanup: "/api/sessions/cleanup",
  sessionsDelete: "/api/sessions/delete",
  archivedSessions: "/api/archived-sessions",

  // Data
  allData: "/api/all-data",
  topGmv: "/api/top-gmv",

  // History
  historyTimeslots: "/api/history/timeslots",
  historyData: "/api/history/data",

  // Overview
  overviewLive: "/api/overview/live",
  overviewHistory: "/api/overview/history",
  overviewSessions: "/api/overview/sessions",

  // Analytics
  analyticsTopProducts: "/api/analytics/top-products",
  analyticsCategoryDist: "/api/analytics/category-distribution",
  itemAnalytics: (id: string) => `/api/item-analytics/${id}`,

  // Auth
  me: "/api/me",
  login: "/auth/login",
  adminLogin: "/admin/login",
  logout: "/logout",

  // Users
  users: "/api/users",
  brandUsers: "/api/brand-users",
  staffSearch: "/api/staff/search",

  // Brand
  brandGmvData: "/api/brand/gmv-data",

  // Config
  config: "/api/config",
  cacheStatus: "/api/cache-status",
  sync: "/api/sync",
  refreshDeallist: "/api/refresh-deallist",
  autoSyncStatus: "/api/auto-sync/status",
  autoSyncStart: "/api/auto-sync/start",
  autoSyncStop: "/api/auto-sync/stop",

  // Host
  hostSyncSchedule: "/api/host/sync-schedule",
  hostPerformance: "/api/host/performance",
  hostExport: "/api/host/export",

  // Fix History
  fixHistoryRecords: "/api/fix-history/records",
  fixHistoryUpdate: "/api/fix-history/update",
  fixHistoryUpdateSession: "/api/fix-history/update-session",
  fixHistoryDeleteSession: "/api/fix-history/delete-session",
} as const;
