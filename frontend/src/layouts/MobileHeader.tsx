import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { Menu, X, LayoutDashboard, BarChart3, Clock, Users, Wrench, Settings } from "lucide-react";
import { useAuthStore } from "@/store/auth.store";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/analytics", label: "Analytics", icon: BarChart3 },
  { path: "/history", label: "History", icon: Clock },
  { path: "/host-performance", label: "Host Performance", icon: Users },
  { path: "/fix-history", label: "Fix History", icon: Wrench },
];

export function MobileHeader() {
  const [menuOpen, setMenuOpen] = useState(false);
  const user = useAuthStore((s) => s.user);

  return (
    <>
      <header className="fixed top-0 left-0 right-0 z-50 flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 md:hidden">
        <button onClick={() => setMenuOpen(true)} className="text-slate-600">
          <Menu className="h-6 w-6" />
        </button>
        <span className="text-sm font-semibold text-slate-900">BeyondK Dashboard</span>
        <div className="w-6" />
      </header>

      {menuOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/40 md:hidden"
          onClick={() => setMenuOpen(false)}
        >
          <nav
            className="absolute left-0 top-0 h-full w-64 bg-white p-4 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-6 flex items-center justify-between">
              <span className="text-lg font-semibold">Menu</span>
              <button onClick={() => setMenuOpen(false)}>
                <X className="h-5 w-5 text-slate-600" />
              </button>
            </div>

            <div className="flex flex-col gap-1">
              {navItems.map(({ path, label, icon: Icon }) => (
                <Link
                  key={path}
                  to={path}
                  onClick={() => setMenuOpen(false)}
                  className="flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium text-slate-600 hover:bg-slate-100"
                >
                  <Icon className="h-5 w-5" />
                  <span>{label}</span>
                </Link>
              ))}
              {user?.role === "bod" && (
                <Link
                  to="/settings"
                  onClick={() => setMenuOpen(false)}
                  className="flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium text-slate-600 hover:bg-slate-100"
                >
                  <Settings className="h-5 w-5" />
                  <span>Settings</span>
                </Link>
              )}
            </div>
          </nav>
        </div>
      )}
    </>
  );
}
