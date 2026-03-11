import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { authService } from "@/services/auth.service";

export function AdminLoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await authService.adminLogin(password);
      if (data.success) {
        navigate({ to: "/dashboard" });
      } else {
        setError(data.message || "Sai mật khẩu");
      }
    } catch {
      setError("Lỗi kết nối");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0f0f23] px-4">
      <div className="w-full max-w-[400px]">
        <div className="rounded-[20px] border border-[#3f3f5a] bg-[#252545] px-10 py-10 text-center">
          {/* Logo */}
          <div className="mx-auto mb-6 flex h-[72px] w-[72px] items-center justify-center rounded-2xl bg-gradient-to-br from-[#667eea] to-[#764ba2] text-4xl">
            🔐
          </div>

          <h1 className="mb-2 text-2xl font-bold text-white">BeyondK Network</h1>
          <p className="mb-8 text-sm text-[#a0a0c0]">
            Đăng nhập để truy cập Dashboard
          </p>

          {error && (
            <div className="mb-6 rounded-lg border border-red-500 bg-red-500/10 px-4 py-3 text-sm text-red-500">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="mb-6 text-left">
              <label className="mb-2 block text-sm font-medium text-[#a0a0c0]">
                Mật khẩu
              </label>
              <input
                type="password"
                placeholder="Nhập mật khẩu admin"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-[10px] border border-[#3f3f5a] bg-[#0f0f23] px-4 py-4 text-base text-white transition-colors focus:border-indigo-500 focus:outline-none"
                autoFocus
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-[10px] bg-gradient-to-br from-[#667eea] to-[#764ba2] px-4 py-4 text-base font-semibold text-white transition-all hover:-translate-y-0.5 hover:shadow-[0_8px_25px_rgba(99,102,241,0.3)] disabled:opacity-50"
            >
              {loading ? "Đang đăng nhập..." : "Đăng nhập"}
            </button>
          </form>

          <Link
            to="/"
            className="mt-6 inline-block text-sm text-[#a0a0c0] transition-colors hover:text-indigo-400"
          >
            ← Về trang chủ
          </Link>
        </div>
      </div>
    </div>
  );
}
