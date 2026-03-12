import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useToastStore } from "@/store/toast.store";
import { Settings, Users, RefreshCw, Trash2, Pencil, Plus, Loader2, PlayCircle, StopCircle } from "lucide-react";
import { FixHistoryPage } from "@/pages/FixHistoryPage";

interface Session {
  session_id: string;
  session_title: string;
}

interface AdminUser {
  id: number;
  email: string;
  name: string;
  role: string;
}

interface BrandUser {
  id: number;
  email: string;
  full_name: string;
  shop_ids: string[];
  brand_label: string;
}

export function SettingsPage() {
  
  const showToast = useToastStore((s) => s.showToast);
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"settings" | "fix-history">("settings");

  // Session state
  const [selectedSessions, setSelectedSessions] = useState<Set<string>>(new Set());

  // DealList state
  const [dlUrl, setDlUrl] = useState("");
  const [dlSheets, setDlSheets] = useState<string[]>([]);
  const [dlSheet, setDlSheet] = useState("");

  // DealList 2 state
  const [dl2Url, setDl2Url] = useState("");
  const [dl2Sheets, setDl2Sheets] = useState<string[]>([]);
  const [dl2Sheet, setDl2Sheet] = useState("");
  const [sessionDeallist, setSessionDeallist] = useState<Record<string, number>>({});
  const [moreSessionId, setMoreSessionId] = useState("");

  // User state
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserRole, setNewUserRole] = useState("admin");

  // Brand user state
  const [brandEmail, setBrandEmail] = useState("");
  const [brandPassword, setBrandPassword] = useState("");
  const [brandName, setBrandName] = useState("");
  const [brandShopIds, setBrandShopIds] = useState("");
  const [brandLabel, setBrandLabel] = useState("");

  // Queries
  const { data: sessionsData } = useQuery({
    queryKey: ["admin-sessions"],
    queryFn: () => api.get<{ success: boolean; sessions: Session[] }>("/api/sessions"),
  });

  const { data: usersData } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => api.get<{ success: boolean; users: AdminUser[] }>("/api/users"),
  });

  const { data: brandUsersData } = useQuery({
    queryKey: ["brand-users"],
    queryFn: () => api.get<{ success: boolean; users: BrandUser[] }>("/api/brand-users"),
  });

  // Deal list counts
  const { data: deallistCountData } = useQuery({
    queryKey: ["deallist-count"],
    queryFn: () => api.get<{ success: boolean; deallist1_count: number; deallist2_count: number }>("/api/deallist-count"),
  });

  // Session-deallist mapping
  const { data: sessionDeallistData } = useQuery({
    queryKey: ["session-deallist"],
    queryFn: () => api.get<{ success: boolean; mapping: Record<string, number> }>("/api/session-deallist"),
  });

  // Sync sessionDeallist state from query
  useEffect(() => {
    if (sessionDeallistData?.success) setSessionDeallist(sessionDeallistData.mapping);
  }, [sessionDeallistData]);

  // Brands thuộc More data
  const { data: moreBrandsData, isFetching: isFetchingMoreBrands } = useQuery({
    queryKey: ["more-brands", moreSessionId],
    queryFn: () => api.get<{ success: boolean; brands: string[] }>(`/api/more-brands?session_id=${moreSessionId}`),
    enabled: !!moreSessionId,
  });
  const moreBrands = moreBrandsData?.success ? moreBrandsData.brands : null;

  // Auto-sync status
  const { data: autoSyncData } = useQuery({
    queryKey: ["auto-sync-status"],
    queryFn: () => api.get<{ success: boolean; active: boolean; next_run?: string }>("/api/auto-sync/status"),
    refetchInterval: 10000,
  });
  const isAutoSyncActive = autoSyncData?.active ?? false;

  const sessions = sessionsData?.success ? sessionsData.sessions : [];
  const users = usersData?.success ? usersData.users : [];
  const brandUsers = brandUsersData?.success ? brandUsersData.users : [];

  // Mutations
  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      api.post("/api/session-rename", { session_id: id, new_title: title }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-sessions"] });
      showToast("Đã đổi tên session", "success");
    },
  });

  const deleteSessionsMutation = useMutation({
    mutationFn: () =>
      api.post("/api/sessions/delete", { session_ids: Array.from(selectedSessions) }),
    onSuccess: () => {
      setSelectedSessions(new Set());
      queryClient.invalidateQueries({ queryKey: ["admin-sessions"] });
      showToast("Đã xóa sessions", "success");
    },
  });

  const refreshDeallistMutation = useMutation({
    mutationFn: () => api.post("/api/refresh-deallist", { url: dlUrl, sheet_name: dlSheet }),
    onSuccess: () => showToast("Đã refresh deal list", "success"),
    onError: () => showToast("Lỗi refresh", "error"),
  });

  const refreshDeallist2Mutation = useMutation({
    mutationFn: () => api.post("/api/refresh-deallist2", { url: dl2Url, sheet_name: dl2Sheet }),
    onSuccess: () => showToast("Đã refresh deal list 2", "success"),
    onError: () => showToast("Lỗi refresh deal list 2", "error"),
  });

  const cleanupMutation = useMutation({
    mutationFn: () => api.post<{ success: boolean; message?: string }>("/api/sessions/cleanup", {}),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["admin-sessions"] });
      showToast(data.message || "Đã dọn dẹp sessions cũ", "success");
    },
    onError: () => showToast("Lỗi cleanup", "error"),
  });

  const autoSyncStartMutation = useMutation({
    mutationFn: () => api.post("/api/auto-sync/start", {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auto-sync-status"] });
      showToast("Auto-sync đã bật", "success");
    },
    onError: () => showToast("Lỗi bật auto-sync", "error"),
  });

  const autoSyncStopMutation = useMutation({
    mutationFn: () => api.post("/api/auto-sync/stop", {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auto-sync-status"] });
      showToast("Auto-sync đã tắt", "info");
    },
    onError: () => showToast("Lỗi tắt auto-sync", "error"),
  });

  const setDeallistMutation = useMutation({
    mutationFn: ({ sessionId, deallistId }: { sessionId: string; deallistId: number }) =>
      api.post("/api/session-deallist", { session_id: sessionId, deallist_id: deallistId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["session-deallist"] }),
  });

  const addUserMutation = useMutation({
    mutationFn: () => api.post("/api/users", { email: newUserEmail, role: newUserRole }),
    onSuccess: () => {
      setNewUserEmail("");
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      showToast("Đã thêm user", "success");
    },
  });

  const deleteUserMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/api/users/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      showToast("Đã xóa user", "success");
    },
  });

  const createBrandUserMutation = useMutation({
    mutationFn: () =>
      api.post("/api/brand-users", {
        email: brandEmail,
        password: brandPassword,
        full_name: brandName,
        shop_ids: brandShopIds.split(",").map((s) => s.trim()).filter(Boolean),
        brand_label: brandLabel,
      }),
    onSuccess: () => {
      setBrandEmail("");
      setBrandPassword("");
      setBrandName("");
      setBrandShopIds("");
      setBrandLabel("");
      queryClient.invalidateQueries({ queryKey: ["brand-users"] });
      showToast("Đã tạo brand user", "success");
    },
  });

  const deleteBrandUserMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/api/brand-users/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["brand-users"] });
      showToast("Đã xóa brand user", "success");
    },
  });

  const toggleSession = (id: string) => {
    setSelectedSessions((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleRename = (session: Session) => {
    const newTitle = prompt("Tên mới:", session.session_title);
    if (newTitle && newTitle !== session.session_title) {
      renameMutation.mutate({ id: session.session_id, title: newTitle });
    }
  };

  const loadSheets = async () => {
    if (!dlUrl) return;
    try {
      const data = await api.post<{ success: boolean; sheets: { name: string }[] }>("/api/get-sheet-names", { url: dlUrl });
      if (data.success) setDlSheets(data.sheets.map((s) => s.name));
    } catch {
      showToast("Lỗi load sheets", "error");
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
        <Settings className="h-6 w-6" />
        Settings
      </h1>

      {/* Tabs */}
      <div className="mb-6 flex gap-2 border-b border-slate-200">
        <button
          onClick={() => setActiveTab("settings")}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === "settings"
              ? "border-b-2 border-blue-600 text-blue-600"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Settings
        </button>
        <button
          onClick={() => setActiveTab("fix-history")}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === "fix-history"
              ? "border-b-2 border-blue-600 text-blue-600"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          🛠️ Fix History
        </button>
      </div>

      {/* Tab Content */}
    {activeTab === "settings" ? (
      <div className="space-y-8">
        {/* GMV Data Info */}
        <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-5">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 text-lg">🐘</span>
            <div className="flex-1">
              <h2 className="font-semibold text-slate-800">GMV Data (PostgreSQL)</h2>
              <p className="text-xs text-slate-500">Dữ liệu GMV được ghi trực tiếp từ <strong>Scraper local</strong> vào PostgreSQL. Scraper tự động cập nhật mỗi 15 phút.</p>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-emerald-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              PostgreSQL · Scraper local
            </div>
          </div>
          {deallistCountData?.success && (
            <div className="mt-3 flex gap-6 text-xs text-slate-500">
              <span>Deal List 1: <strong>{deallistCountData.deallist1_count}</strong> items</span>
              <span>Deal List 2: <strong>{deallistCountData.deallist2_count}</strong> items</span>
            </div>
          )}
        </div>

      {/* Session Management */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Sessions</h2>
        <div className="space-y-2">
          {sessions.map((s) => (
            <div key={`settings-session-${s.session_id}`} className="flex items-center gap-3 rounded-lg border border-slate-100 px-4 py-3">
              <input
                type="checkbox"
                checked={selectedSessions.has(s.session_id)}
                onChange={() => toggleSession(s.session_id)}
                className="h-4 w-4 rounded border-slate-300"
              />
              <span className="flex-1 text-sm font-medium text-slate-700">{s.session_title || `Session ${s.session_id}`}</span>
              {/* DealList selector per session */}
              <select
                value={sessionDeallist[s.session_id] ?? 1}
                onChange={(e) => {
                  const dl = Number(e.target.value);
                  setSessionDeallist(prev => ({ ...prev, [s.session_id]: dl }));
                  setDeallistMutation.mutate({ sessionId: s.session_id, deallistId: dl });
                }}
                className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600"
              >
                <option value={1}>Deal List 1</option>
                <option value={2}>Deal List 2</option>
              </select>
              <button onClick={() => handleRename(s)} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-blue-600">
                <Pencil className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
        {selectedSessions.size > 0 && (
          <button
            onClick={() => {
              if (confirm(`Xóa ${selectedSessions.size} session?`)) deleteSessionsMutation.mutate();
            }}
            disabled={deleteSessionsMutation.isPending}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            <Trash2 className="h-4 w-4" />
            Xóa {selectedSessions.size} session
          </button>
        )}
      </div>

      {/* Brands thuộc More */}
      <div className="rounded-xl border border-blue-100 bg-blue-50 p-6">
        <h2 className="mb-2 flex items-center gap-2 text-lg font-semibold text-slate-800">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500 text-xs text-white">ℹ️</span>
          Brands thuộc More (chưa có tag Live)
        </h2>
        <p className="mb-4 text-sm text-slate-600">
          Các brands có item nằm trong danh sách "more" — cần liên hệ brand gắn tag giá live.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={moreSessionId}
            onChange={(e) => setMoreSessionId(e.target.value)}
            className="flex-1 min-w-[200px] rounded-lg border border-blue-200 bg-white px-4 py-2 text-sm text-slate-700 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">-- Chọn Session --</option>
            {sessions.map((s) => (
              <option key={`settings-select-session-${s.session_id}`} value={s.session_id}>
                [{s.session_id}] {s.session_title || `Session ${s.session_id}`}
              </option>
            ))}
          </select>
          <button
            onClick={() => {
              if (moreBrands && moreBrands.length > 0) {
                navigator.clipboard.writeText(moreBrands.join(", "));
                showToast("Đã copy danh sách brands!", "success");
              }
            }}
            disabled={!moreBrands || moreBrands.length === 0}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
            Copy
          </button>
        </div>
        <div className="mt-4 text-sm text-slate-600">
          {!moreSessionId ? (
            "Chọn session để xem"
          ) : isFetchingMoreBrands ? (
            "Đang tải..."
          ) : moreBrands && moreBrands.length > 0 ? (
            <div className="rounded-lg bg-white p-3 text-slate-700 border border-blue-200">
              {moreBrands.join(", ")}
            </div>
          ) : (
            "Không có brand nào trong danh sách more của session này."
          )}
        </div>
      </div>

      {/* Deal List */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Deal List</h2>
        <div className="space-y-3">
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Google Sheet URL..."
              value={dlUrl}
              onChange={(e) => setDlUrl(e.target.value)}
              className="flex-1 rounded-lg border border-slate-200 px-4 py-2 text-sm focus:border-blue-400 focus:outline-none"
            />
            <button onClick={loadSheets} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
              Load Sheets
            </button>
          </div>
          {dlSheets.length > 0 && (
            <div className="flex gap-3">
              <select
                value={dlSheet}
                onChange={(e) => setDlSheet(e.target.value)}
                className="flex-1 rounded-lg border border-slate-200 px-4 py-2 text-sm"
              >
                <option value="">Chọn sheet...</option>
                {dlSheets.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <button
                onClick={() => refreshDeallistMutation.mutate()}
                disabled={!dlSheet || refreshDeallistMutation.isPending}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {refreshDeallistMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Refresh
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Deal List 2 */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-1 text-lg font-semibold text-slate-800">Deal List 2</h2>
        <p className="mb-4 text-xs text-slate-400">Sheet riêng cho deal list thứ hai (nếu có)</p>
        <div className="space-y-3">
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Google Sheet URL (Deal List 2)..."
              value={dl2Url}
              onChange={(e) => setDl2Url(e.target.value)}
              className="flex-1 rounded-lg border border-slate-200 px-4 py-2 text-sm focus:border-blue-400 focus:outline-none"
            />
            <button
              onClick={async () => {
                if (!dl2Url) return;
                try {
                  const data = await api.post<{ success: boolean; sheets: { name: string }[] }>("/api/get-sheet-names", { url: dl2Url });
                  if (data.success) setDl2Sheets(data.sheets.map((s) => s.name));
                } catch { showToast("Lỗi load sheets", "error"); }
              }}
              className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Load Sheets
            </button>
          </div>
          {dl2Sheets.length > 0 && (
            <div className="flex gap-3">
              <select
                value={dl2Sheet}
                onChange={(e) => setDl2Sheet(e.target.value)}
                className="flex-1 rounded-lg border border-slate-200 px-4 py-2 text-sm"
              >
                <option value="">Chọn sheet...</option>
                {dl2Sheets.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <button
                onClick={() => refreshDeallist2Mutation.mutate()}
                disabled={!dl2Sheet || refreshDeallist2Mutation.isPending}
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {refreshDeallist2Mutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Refresh
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Auto-sync */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">Auto-sync</h2>
            <p className="mt-0.5 text-xs text-slate-400">Tự động sync data mỗi 5 phút</p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${isAutoSyncActive ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${isAutoSyncActive ? "bg-emerald-500 animate-pulse" : "bg-slate-400"}`} />
              {isAutoSyncActive ? "Đang chạy" : "Đã dừng"}
            </span>
            {isAutoSyncActive ? (
              <button
                onClick={() => autoSyncStopMutation.mutate()}
                disabled={autoSyncStopMutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg bg-red-50 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-100 disabled:opacity-50"
              >
                {autoSyncStopMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <StopCircle className="h-4 w-4" />}
                Dừng
              </button>
            ) : (
              <button
                onClick={() => autoSyncStartMutation.mutate()}
                disabled={autoSyncStartMutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {autoSyncStartMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
                Bật
              </button>
            )}
          </div>
        </div>
        {autoSyncData?.next_run && (
          <p className="mt-3 text-xs text-slate-400">Lần sync tiếp: {autoSyncData.next_run}</p>
        )}
      </div>

      {/* Sessions Cleanup */}
      <div className="rounded-xl border border-amber-100 bg-amber-50 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">Dọn dẹp Sessions</h2>
            <p className="mt-0.5 text-xs text-slate-500">Xóa các session cũ không còn cần thiết</p>
          </div>
          <button
            onClick={() => {
              if (confirm("Dọn dẹp các session cũ? Hành động này không thể hoàn tác."))
                cleanupMutation.mutate();
            }}
            disabled={cleanupMutation.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {cleanupMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            Cleanup
          </button>
        </div>
      </div>

      {/* User Management */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-800">
          <Users className="h-5 w-5" />
          Users
        </h2>

        <div className="mb-4 flex gap-3">
          <input
            type="email"
            placeholder="Email..."
            value={newUserEmail}
            onChange={(e) => setNewUserEmail(e.target.value)}
            className="flex-1 rounded-lg border border-slate-200 px-4 py-2 text-sm"
          />
          <select
            value={newUserRole}
            onChange={(e) => setNewUserRole(e.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
          >
            <option value="admin">Admin</option>
            <option value="bod">BOD</option>
          </select>
          <button
            onClick={() => addUserMutation.mutate()}
            disabled={!newUserEmail || addUserMutation.isPending}
            className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            Thêm
          </button>
        </div>

        <div className="divide-y divide-slate-100 rounded-lg border border-slate-100">
          {users.map((u) => (
            <div key={u.id} className="flex items-center justify-between px-4 py-3">
              <div>
                <p className="text-sm font-medium text-slate-700">{u.email}</p>
                <p className="text-xs text-slate-400">{u.role}</p>
              </div>
              <button
                onClick={() => {
                  if (confirm(`Xóa user ${u.email}?`)) deleteUserMutation.mutate(u.id);
                }}
                className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Brand Users */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Brand Users</h2>

        <div className="mb-4 grid grid-cols-2 gap-3">
          <input placeholder="Email" value={brandEmail} onChange={(e) => setBrandEmail(e.target.value)} className="rounded-lg border border-slate-200 px-4 py-2 text-sm" />
          <input placeholder="Password" type="password" value={brandPassword} onChange={(e) => setBrandPassword(e.target.value)} className="rounded-lg border border-slate-200 px-4 py-2 text-sm" />
          <input placeholder="Tên" value={brandName} onChange={(e) => setBrandName(e.target.value)} className="rounded-lg border border-slate-200 px-4 py-2 text-sm" />
          <input placeholder="Brand Label" value={brandLabel} onChange={(e) => setBrandLabel(e.target.value)} className="rounded-lg border border-slate-200 px-4 py-2 text-sm" />
          <input placeholder="Shop IDs (cách nhau bởi dấu phẩy)" value={brandShopIds} onChange={(e) => setBrandShopIds(e.target.value)} className="col-span-2 rounded-lg border border-slate-200 px-4 py-2 text-sm" />
          <button
            onClick={() => createBrandUserMutation.mutate()}
            disabled={!brandEmail || !brandPassword || createBrandUserMutation.isPending}
            className="col-span-2 inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            Tạo Brand User
          </button>
        </div>

        <div className="divide-y divide-slate-100 rounded-lg border border-slate-100">
          {brandUsers.map((u) => (
            <div key={u.id} className="flex items-center justify-between px-4 py-3">
              <div>
                <p className="text-sm font-medium text-slate-700">{u.full_name || u.email}</p>
                <p className="text-xs text-slate-400">
                  {u.brand_label} · {(u.shop_ids || []).join(", ")}
                </p>
              </div>
              <button
                onClick={() => {
                  if (confirm(`Xóa brand user ${u.email}?`)) deleteBrandUserMutation.mutate(u.id);
                }}
                className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </div>
      </div>
    ) : (
      <FixHistoryPage />
    )}
    </div>
  );
}
