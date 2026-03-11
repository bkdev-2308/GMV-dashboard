import { useEffect } from "react";
import { Outlet } from "@tanstack/react-router";
import { Sidebar } from "./Sidebar";
import { MobileHeader } from "./MobileHeader";
import { useSessionStore } from "@/store/session.store";
import { useAuthStore } from "@/store/auth.store";
import { authService } from "@/services/auth.service";
import { cn } from "@/utils/cn";

export function AppLayout() {
  const sidebarExpanded = useSessionStore((s) => s.sidebarExpanded);
  const setUser = useAuthStore((s) => s.setUser);
  const setLoading = useAuthStore((s) => s.setLoading);

  // Fetch current user from Flask session on mount
  useEffect(() => {
    authService.getCurrentUser().then((res) => {
      if (res.success && res.user) {
        setUser(res.user);
      } else {
        setUser(null);
      }
    }).catch(() => {
      setLoading(false);
    });
  }, [setUser, setLoading]);

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Desktop sidebar */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {/* Mobile header */}
      <MobileHeader />

      {/* Main content */}
      <main
        className={cn(
          "flex-1 transition-all duration-300 pt-14 md:pt-0",
          sidebarExpanded ? "md:ml-60" : "md:ml-16"
        )}
      >
        <div className="p-4 md:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
