import { useQuery } from "@tanstack/react-query";
import { sessionService } from "@/services/session.service";
import { useSessionStore } from "@/store/session.store";

export function SessionFilter() {
  const { currentSessionId, setCurrentSession } = useSessionStore();

  const { data: sessionsData } = useQuery({
    queryKey: ["sessions"],
    queryFn: sessionService.getSessions,
  });

  const sessions = sessionsData?.success ? sessionsData.sessions : [];

  return (
    <div className="flex flex-wrap items-center gap-3">
      <select
        value={currentSessionId}
        onChange={(e) => setCurrentSession(e.target.value)}
        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
      >
        <option value="">Chọn phiên</option>
        {sessions.map((s) => (
          <option key={s.session_id} value={s.session_id}>
            {s.session_title || `Session ${s.session_id}`}
          </option>
        ))}
      </select>
    </div>
  );
}
