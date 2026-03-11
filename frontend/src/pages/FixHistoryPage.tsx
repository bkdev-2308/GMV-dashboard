import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useToastStore } from "@/store/toast.store";
import { Spinner } from "@/components/ui/Spinner";
import {
  ArrowLeft,
  Pencil,
  Trash2,
  Save,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { Link } from "@tanstack/react-router";

interface ArchivedSession {
  session_id: string;
  session_title: string;
  timeslot_count: number;
}

export function FixHistoryPage() {
  const [editingSession, setEditingSession] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const showToast = useToastStore((s) => s.showToast);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["archived-sessions"],
    queryFn: () =>
      api.get<{ success: boolean; sessions: ArchivedSession[] }>(
        "/api/archived-sessions",
      ),
  });

  const sessions = data?.success ? data.sessions : [];

  const updateMutation = useMutation({
    mutationFn: ({ sessionId, title }: { sessionId: string; title: string }) =>
      api.post<{ success: boolean; message: string }>(
        "/api/fix-history/update-session",
        {
          session_id: sessionId,
          new_title: title,
        },
      ),
    onSuccess: (result) => {
      if (result.success) {
        showToast("Cập nhật thành công!", "success");
        setEditingSession(null);
        queryClient.invalidateQueries({ queryKey: ["archived-sessions"] });
      } else {
        showToast(result.message || "Lỗi cập nhật", "error");
      }
    },
    onError: () => showToast("Lỗi kết nối", "error"),
  });

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) =>
      api.post<{ success: boolean; message: string }>(
        "/api/fix-history/delete-session",
        {
          session_id: sessionId,
        },
      ),
    onSuccess: (result) => {
      if (result.success) {
        showToast("Đã xóa session!", "success");
        queryClient.invalidateQueries({ queryKey: ["archived-sessions"] });
      } else {
        showToast(result.message || "Lỗi xóa", "error");
      }
    },
    onError: () => showToast("Lỗi kết nối", "error"),
  });

  const handleEdit = (session: ArchivedSession) => {
    setEditingSession(session.session_id);
    setNewTitle(session.session_title);
  };

  const handleSave = (sessionId: string) => {
    if (!newTitle.trim()) return;
    updateMutation.mutate({ sessionId, title: newTitle.trim() });
  };

  const handleDelete = (session: ArchivedSession) => {
    if (
      !confirm(
        `Xóa session "${session.session_title}"?\n\nSession có ${session.timeslot_count} timeslot sẽ bị xóa hoàn toàn.`,
      )
    ) {
      return;
    }
    deleteMutation.mutate(session.session_id);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          to="/dashboard"
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <h1 className="text-2xl font-bold text-slate-900">Fix History</h1>
      </div>

      {/* Warning */}
      <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
        <div className="text-sm text-amber-800">
          <p className="font-semibold">Công cụ quản trị</p>
          <p className="mt-1">
            Dùng để sửa tên hoặc xóa session trong lịch sử. Thao tác xóa không
            thể hoàn tác.
          </p>
        </div>
      </div>

      {/* Sessions List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Spinner size="lg" />
        </div>
      ) : sessions.length > 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-6 py-4">
            <h2 className="text-sm font-semibold text-slate-700">
              Archived Sessions ({sessions.length})
            </h2>
          </div>

          <div className="divide-y divide-slate-100">
            {sessions.map((session) => (
              <div key={session.session_id} className="px-6 py-4">
                {editingSession === session.session_id ? (
                  <div className="flex items-center gap-3">
                    <input
                      type="text"
                      value={newTitle}
                      onChange={(e) => setNewTitle(e.target.value)}
                      className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleSave(session.session_id);
                        if (e.key === "Escape") setEditingSession(null);
                      }}
                    />
                    <button
                      onClick={() => handleSave(session.session_id)}
                      disabled={updateMutation.isPending}
                      className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {updateMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                    </button>
                    <button
                      onClick={() => setEditingSession(null)}
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
                    >
                      Hủy
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-slate-800">
                        {session.session_title}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-400">
                        {session.timeslot_count} timeslot · ID:{" "}
                        {session.session_id}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleEdit(session)}
                        className="rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                        title="Sửa tên"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(session)}
                        disabled={deleteMutation.isPending}
                        className="rounded-md p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"
                        title="Xóa session"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
          Không có session nào trong lịch sử
        </div>
      )}
    </div>
  );
}
