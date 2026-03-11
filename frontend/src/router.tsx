import { lazy } from "react";
import { createRouter, createRootRoute, createRoute } from "@tanstack/react-router";
import { AppLayout } from "@/layouts/AppLayout";

// Lazy-loaded pages
const DashboardPage = lazy(() => import("@/pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const LoginPage = lazy(() => import("@/pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const AdminLoginPage = lazy(() => import("@/pages/AdminLoginPage").then((m) => ({ default: m.AdminLoginPage })));
const AnalyticsPage = lazy(() => import("@/pages/AnalyticsPage").then((m) => ({ default: m.AnalyticsPage })));
const HistoryPage = lazy(() => import("@/pages/HistoryPage").then((m) => ({ default: m.HistoryPage })));
const HostPerformancePage = lazy(() => import("@/pages/HostPerformancePage").then((m) => ({ default: m.HostPerformancePage })));
const FixHistoryPage = lazy(() => import("@/pages/FixHistoryPage").then((m) => ({ default: m.FixHistoryPage })));
const SettingsPage = lazy(() => import("@/pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const BrandPage = lazy(() => import("@/pages/BrandPage").then((m) => ({ default: m.BrandPage })));
const StaffPage = lazy(() => import("@/pages/StaffPage").then((m) => ({ default: m.StaffPage })));
const LandingPage = lazy(() => import("@/pages/LandingPage").then((m) => ({ default: m.LandingPage })));

const rootRoute = createRootRoute();

// Public routes
const landingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: LandingPage,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginPage,
});

const adminLoginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/login",
  component: AdminLoginPage,
});

// App layout (authenticated)
const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app",
  component: AppLayout,
});

const dashboardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/dashboard",
  component: DashboardPage,
});

const analyticsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/analytics",
  component: AnalyticsPage,
});

const historyRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/history",
  component: HistoryPage,
});

const hostPerformanceRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/host-performance",
  component: HostPerformancePage,
});

const fixHistoryRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/fix-history",
  component: FixHistoryPage,
});

const settingsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/settings",
  component: SettingsPage,
});

const brandRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/brand",
  component: BrandPage,
});

const staffRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/staff",
  component: StaffPage,
});

const routeTree = rootRoute.addChildren([
  landingRoute,
  loginRoute,
  adminLoginRoute,
  appRoute.addChildren([
    dashboardRoute,
    analyticsRoute,
    historyRoute,
    hostPerformanceRoute,
    fixHistoryRoute,
    settingsRoute,
    brandRoute,
    staffRoute,
  ]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
