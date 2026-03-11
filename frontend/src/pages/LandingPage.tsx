import { Link } from "@tanstack/react-router";

export function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-900">
      {/* Particles */}
      <div className="absolute inset-0">
        {Array.from({ length: 20 }).map((_, i) => (
          <div
            key={i}
            className="absolute rounded-full bg-white/10"
            style={{
              width: `${Math.random() * 6 + 2}px`,
              height: `${Math.random() * 6 + 2}px`,
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animation: `float ${Math.random() * 15 + 15}s linear infinite`,
              animationDelay: `${Math.random() * 10}s`,
            }}
          />
        ))}
      </div>

      {/* Navbar */}
      <nav className="relative z-10 flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-3">
          <img src="/static/BK_logo.ico" alt="BeyondK" className="h-10 w-10" />
          <span className="text-lg font-bold text-white">BeyondK Network</span>
        </div>
        <Link
          to="/login"
          className="rounded-lg bg-white/10 px-6 py-2 text-sm font-medium text-white backdrop-blur-sm transition-colors hover:bg-white/20"
        >
          Đăng nhập
        </Link>
      </nav>

      {/* Hero */}
      <div className="relative z-10 flex min-h-[70vh] flex-col items-center justify-center px-6 text-center">
        <h1 className="bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-5xl font-bold leading-tight text-transparent md:text-7xl">
          BeyondK
          <br />
          Dashboard
        </h1>
        <p className="mt-6 max-w-lg text-lg text-slate-400">
          Nền tảng phân tích dữ liệu livestream affiliate Shopee
        </p>
        <Link
          to="/login"
          className="mt-8 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-transform hover:scale-105"
        >
          Bắt đầu ngay
        </Link>
      </div>

      {/* Float animation */}
      <style>{`
        @keyframes float {
          0% { transform: translateY(100vh) rotate(0deg); opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { transform: translateY(-10vh) rotate(720deg); opacity: 0; }
        }
      `}</style>
    </div>
  );
}
