import { Link, useMatchRoute } from "@tanstack/react-router";
import {
  LayoutDashboard,
  BarChart3,
  Clock,
  Users,
  Settings,
} from "lucide-react";
import { cn } from "@/utils/cn";
import { useSessionStore } from "@/store/session.store";
import { useAuthStore } from "@/store/auth.store";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/analytics", label: "Analytics", icon: BarChart3 },
  { path: "/history", label: "History", icon: Clock },
  { path: "/host-performance", label: "Host Performance", icon: Users },
  // { path: "/fix-history", label: "Fix History", icon: Wrench },
];

export function Sidebar() {
  const { sidebarExpanded, toggleSidebar } = useSessionStore();
  const user = useAuthStore((s) => s.user);
  const matchRoute = useMatchRoute();

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-50 flex h-screen flex-col items-center border-r border-slate-200 bg-white py-4 transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]",
        sidebarExpanded ? "w-60 items-start px-4" : "w-16"
      )}
    >
      {/* Logo */}
      <button
        onClick={toggleSidebar}
        className={cn(
          "mb-8 flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded-xl transition-all",
          sidebarExpanded && "w-full justify-start pl-3"
        )}
      >
        <img
          src="/static/BK_logo.ico"
          alt="BeyondK"
          className="h-10 w-10 object-contain"
        />
        {sidebarExpanded && (
          <span className="ml-2.5 text-base font-semibold text-slate-900">
            BeyondK Network
          </span>
        )}
      </button>

      {/* Navigation */}
      <nav className="flex w-full flex-col gap-1">
        {navItems.map(({ path, label, icon: Icon }) => {
          const isActive = matchRoute({ to: path, fuzzy: true });
          return (
            <Link
              key={path}
              to={path}
              className={cn(
                "flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100",
                isActive && "bg-blue-50 text-blue-600",
                !sidebarExpanded && "justify-center"
              )}
              title={label}
            >
              <Icon className="h-5 w-5 shrink-0" />
              {sidebarExpanded && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Settings - BOD only */}
      {user?.role === "bod" && (
        <div className="mt-auto w-full">
          <Link
            to="/settings"
            className={cn(
              "flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100",
              matchRoute({ to: "/settings" }) && "bg-blue-50 text-blue-600",
              !sidebarExpanded && "justify-center"
            )}
            title="Settings"
          >
            <Settings className="h-5 w-5 shrink-0" />
            {sidebarExpanded && <span>Settings</span>}
          </Link>
        </div>
      )}
    </aside>
  );
}
