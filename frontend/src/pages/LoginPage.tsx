import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { authService } from "@/services/auth.service";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleGoogleLogin = () => {
    authService.googleLogin();
  };

  const handleBrandLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await authService.brandLogin(email, password);
      if (result.success) {
        window.location.href = result.redirect || "/brand";
      } else {
        setError(result.message || "Đăng nhập thất bại");
      }
    } catch {
      setError("Lỗi kết nối");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-indigo-500 to-purple-600 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl">
        <div className="mb-8 text-center">
          <img src="/static/BK_logo.ico" alt="BeyondK" className="mx-auto mb-4 h-16 w-16" />
          <h1 className="text-2xl font-bold text-slate-900">BeyondK Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">Đăng nhập để tiếp tục</p>
        </div>

        {/* Google Login */}
        <button
          onClick={handleGoogleLogin}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
        >
          <img
            src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg"
            alt="Google"
            className="h-5 w-5"
          />
          Đăng nhập với Google
        </button>

        <div className="my-6 flex items-center gap-3">
          <div className="h-px flex-1 bg-slate-200" />
          <span className="text-xs text-slate-400">HOẶC</span>
          <div className="h-px flex-1 bg-slate-200" />
        </div>

        {/* Brand Login */}
        <form onSubmit={handleBrandLogin} className="space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>
          )}
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-slate-200 px-4 py-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
            required
          />
          <input
            type="password"
            placeholder="Mật khẩu"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-slate-200 px-4 py-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Đang đăng nhập..." : "Đăng nhập Brand"}
          </button>
        </form>

        <div className="mt-6 text-center">
          <Link
            to="/admin/login"
            className="text-sm text-slate-400 transition-colors hover:text-indigo-500"
          >
            Đăng nhập Admin →
          </Link>
        </div>
      </div>
    </div>
  );
}
