import { api } from "./api";
import type {
  SessionsResponse,
  ArchivedSessionsResponse,
  TimeslotsResponse,
  SessionDataResponse,
  HistoryDataResponse,
} from "@/types";

export const sessionService = {
  /** Get active sessions from gmv_data */
  getSessions: () => api.get<SessionsResponse>("/api/sessions"),

  /** Get archived sessions from gmv_history */
  getArchivedSessions: () => api.get<ArchivedSessionsResponse>("/api/archived-sessions"),

  /** Get timeslots for a history session */
  getTimeslots: (sessionId: string) =>
    api.get<TimeslotsResponse>(`/api/history/timeslots?session_id=${sessionId}`),

  /** Get live session data (from gmv_data) */
  getSessionData: (sessionId: string) =>
    api.get<SessionDataResponse>(`/api/all-data?session_id=${sessionId}`),

  /** Get history data at a specific timeslot */
  getHistoryData: (sessionId: string, archivedAt: string) =>
    api.get<HistoryDataResponse>(
      `/api/history/data?session_id=${sessionId}&archived_at=${archivedAt}`
    ),

  /** Rename a session (admin only) */
  renameSession: (sessionId: string, newTitle: string) =>
    api.post<{ success: boolean; message?: string }>("/api/session-rename", {
      session_id: sessionId,
      new_title: newTitle,
    }),

  /** Delete selected sessions (admin only) */
  deleteSessions: (sessionIds: string[]) =>
    api.post<{ success: boolean; message?: string }>("/api/sessions/delete", {
      session_ids: sessionIds,
    }),

  /** Cleanup old sessions - keep only 2 newest */
  cleanupSessions: () =>
    api.post<{ success: boolean; message?: string }>("/api/sessions/cleanup"),
};
