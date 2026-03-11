import type { MeResponse } from "@/types";

export const authService = {
  /** Get current user from Flask session */
  getCurrentUser: async (): Promise<MeResponse> => {
    const res = await fetch("/api/me", { credentials: "include" });
    return res.json();
  },

  /** Admin login - Flask expects form POST to /admin/login */
  adminLogin: async (password: string): Promise<{ success: boolean; message?: string }> => {
    const formData = new URLSearchParams();
    formData.append("password", password);

    const res = await fetch("/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData,
      credentials: "include",
      redirect: "follow",
    });

    // Flask redirects to /admin on success, or re-renders login with error
    // If we end up at /admin (not /admin/login), login was successful
    if (res.redirected && !res.url.includes("/admin/login")) {
      return { success: true };
    }

    // Check if the response contains error in HTML (form-based response)
    const html = await res.text();
    if (html.includes("Mật khẩu không đúng")) {
      return { success: false, message: "Mật khẩu không đúng" };
    }

    // If the URL changed to /admin, success
    if (res.url.includes("/admin") && !res.url.includes("/admin/login")) {
      return { success: true };
    }

    return { success: false, message: "Đăng nhập thất bại" };
  },

  /** Brand login - Flask expects form POST to /login */
  brandLogin: async (
    email: string,
    password: string
  ): Promise<{ success: boolean; redirect?: string; message?: string }> => {
    const formData = new URLSearchParams();
    formData.append("email", email);
    formData.append("password", password);

    const res = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData,
      credentials: "include",
      redirect: "follow",
    });

    // Flask redirects to /brand on success
    if (res.redirected && res.url.includes("/brand")) {
      return { success: true, redirect: "/brand" };
    }

    const html = await res.text();
    if (html.includes("error")) {
      // Try to extract error message
      const match = html.match(/error['"]\s*>\s*([^<]+)/);
      return { success: false, message: match?.[1]?.trim() || "Đăng nhập thất bại" };
    }

    return { success: false, message: "Đăng nhập thất bại" };
  },

  /** Google OAuth - redirect to Google */
  googleLogin: () => {
    window.location.href = "/auth/google";
  },

  /** Logout (admin or Google user) */
  logout: () => {
    window.location.href = "/logout";
  },

  /** Brand logout */
  brandLogout: () => {
    window.location.href = "/brand/logout";
  },
};
