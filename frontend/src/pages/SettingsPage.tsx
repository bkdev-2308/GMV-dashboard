import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useToastStore } from "@/store/toast.store";
import { Settings, Users, RefreshCw, Trash2, Pencil, Plus, Loader2 } from "lucide-react";

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

  // Session state
  const [selectedSessions, setSelectedSessions] = useState<Set<string>>(new Set());

  // DealList state
  const [dlUrl, setDlUrl] = useState("");
  const [dlSheets, setDlSheets] = useState<string[]>([]);
  const [dlSheet, setDlSheet] = useState("");

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

      {/* Session Management */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Sessions</h2>
        <div className="space-y-2">
          {sessions.map((s) => (
            <div key={s.session_id} className="flex items-center gap-3 rounded-lg border border-slate-100 px-4 py-3">
              <input
                type="checkbox"
                checked={selectedSessions.has(s.session_id)}
                onChange={() => toggleSession(s.session_id)}
                className="h-4 w-4 rounded border-slate-300"
              />
              <span className="flex-1 text-sm font-medium text-slate-700">{s.session_title || `Session ${s.session_id}`}</span>
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
  );
}
