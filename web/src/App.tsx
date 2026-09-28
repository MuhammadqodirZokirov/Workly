import { createBrowserRouter, Navigate, Outlet, RouterProvider } from "react-router";

import { AppLayout } from "./components/shared";
import { FullScreenLoader } from "./components/ui";
import { useAuth } from "./lib/auth";
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

/** Kirmagan — xush kelibsiz/kirish; rol yo'q — rol tanlash; aks holda ilova */
function Gate({ need }: { need: "guest" | "noRole" | "app" }) {
  const { me, loading, role } = useAuth();
  if (loading) return <FullScreenLoader />;
  const state = !me ? "guest" : !role ? "noRole" : "app";
  if (state === need) return <Outlet />;
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
  { path: "*", element: <Navigate to="/" replace /> },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
