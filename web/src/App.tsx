import { createBrowserRouter, Navigate, Outlet, RouterProvider } from "react-router";

import { AppLayout } from "./components/shared";
import { FullScreenLoader } from "./components/ui";
import { useAuth } from "./lib/auth";
import { AdminGate, BusinessQueue, VerificationCase, VerificationQueue } from "./pages/admin/AdminPanel";
import { AdminOrderDetail, AdminOrders, AdminPrices, AdminUsers, OpsBoard } from "./pages/admin/Ops";
import EmployerHome from "./pages/employer/EmployerHome";
import NewOrder from "./pages/employer/NewOrder";
import Orders, { OrderDetail } from "./pages/employer/Orders";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import RoleSelect from "./pages/RoleSelect";
import Welcome from "./pages/Welcome";
import WorkerHome from "./pages/worker/WorkerHome";
import WorkerJobs from "./pages/worker/WorkerJobs";
import WorkerProfilePage from "./pages/worker/WorkerProfilePage";

const STAFF = ["moderator", "admin", "super_admin"];

/** Kirmagan — xush kelibsiz/kirish; rol yo'q — rol tanlash; aks holda ilova */
function Gate({ need }: { need: "guest" | "noRole" | "app" }) {
  const { me, loading, role } = useAuth();
  if (loading) return <FullScreenLoader />;
  const state = !me ? "guest" : !role ? "noRole" : "app";
  if (state === need) return <Outlet />;
  if (state !== "guest") {
    // Kirgandan keyin ?next= ga qaytish (masalan, /admin); faqat ichki yo'llar
    const next = new URLSearchParams(window.location.search).get("next");
    if (next?.startsWith("/") && !next.startsWith("//")) return <Navigate to={next} replace />;
    // Faqat xodim (ishchi/employer roli yo'q) — to'g'ridan-to'g'ri admin panelga
    if (state === "noRole" && me!.roles.some((r) => STAFF.includes(r))) return <Navigate to="/admin" replace />;
  }
  return <Navigate to={state === "guest" ? "/welcome" : state === "noRole" ? "/role" : "/"} replace />;
}

function Home() {
  const { role } = useAuth();
  return role === "employer" ? <EmployerHome /> : <WorkerHome />;
}

function RoleOnly({ role, children }: { role: "worker" | "employer"; children: React.ReactNode }) {
  const auth = useAuth();
  return auth.role === role ? <>{children}</> : <Navigate to="/" replace />;
}

const router = createBrowserRouter([
  {
    element: <Gate need="guest" />,
    children: [
      { path: "/welcome", element: <Welcome /> },
      { path: "/login", element: <Login /> },
    ],
  },
  { element: <Gate need="noRole" />, children: [{ path: "/role", element: <RoleSelect /> }] },
  {
    element: <Gate need="app" />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/", element: <Home /> },
          { path: "/jobs", element: <RoleOnly role="worker"><WorkerJobs /></RoleOnly> },
          { path: "/orders", element: <RoleOnly role="employer"><Orders /></RoleOnly> },
          { path: "/profile", element: <Profile /> },
        ],
      },
      { path: "/worker/profile", element: <RoleOnly role="worker"><WorkerProfilePage /></RoleOnly> },
      { path: "/orders/new", element: <RoleOnly role="employer"><NewOrder /></RoleOnly> },
      { path: "/orders/:id", element: <RoleOnly role="employer"><OrderDetail /></RoleOnly> },
      // Botdagi "Batafsil" tugmasi — takliflar ro'yxatiga
      { path: "/offers/:id", element: <Navigate to="/jobs" replace /> },
    ],
  },
  {
    path: "/admin",
    element: <AdminGate />,
    children: [
      { index: true, element: <Navigate to="/admin/board" replace /> },
      { path: "board", element: <OpsBoard /> },
      { path: "orders", element: <AdminOrders /> },
      { path: "orders/:id", element: <AdminOrderDetail /> },
      { path: "users", element: <AdminUsers /> },
      { path: "prices", element: <AdminPrices /> },
      { path: "verifications", element: <VerificationQueue /> },
      { path: "verifications/:id", element: <VerificationCase /> },
      { path: "businesses", element: <BusinessQueue /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
