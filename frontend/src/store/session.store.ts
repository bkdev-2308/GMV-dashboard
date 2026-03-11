import { create } from "zustand";

interface SessionState {
  currentSessionId: string;
  currentArchivedAt: string;
  sidebarExpanded: boolean;
  setCurrentSession: (id: string) => void;
  setCurrentArchivedAt: (archivedAt: string) => void;
  toggleSidebar: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  currentSessionId: "",
  currentArchivedAt: "",
  sidebarExpanded: false,
  setCurrentSession: (id) => set({ currentSessionId: id, currentArchivedAt: "" }),
  setCurrentArchivedAt: (archivedAt) => set({ currentArchivedAt: archivedAt }),
  toggleSidebar: () => set((state) => ({ sidebarExpanded: !state.sidebarExpanded })),
}));
