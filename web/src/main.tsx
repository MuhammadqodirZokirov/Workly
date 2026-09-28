import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ApiError } from "./lib/api";
import { AuthProvider } from "./lib/auth";
import { initTelegram } from "./lib/telegram";

initTelegram();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 4xx — qayta urinish befoyda; tarmoq xatosida 2 marta
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
      refetchOnWindowFocus: true,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
