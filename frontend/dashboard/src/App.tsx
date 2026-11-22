// Dispatcher and admin dashboard (B1-A3-01 shell, B1-A3-04 sign-in and role routing).
import { useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiClient, I18nProvider } from "@amceds/shared";
import { AuthProvider } from "./auth/AuthProvider";
import { HomeRedirect, RequireAuth, RequireRole } from "./auth/guards";
import { AppLayout } from "./layout/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { IncidentPage } from "./incidents/IncidentPage";
import { QueuePage } from "./incidents/QueuePage";
import { AdminPage } from "./pages/placeholders";

export function makeQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true, staleTime: 2_000 } } });
}

/** Providers and routes; the router itself is chosen by the caller (browser, or memory in tests). */
export function Root({ client, queryClient }: { client: ApiClient; queryClient?: QueryClient }) {
  const [queries] = useState(() => queryClient ?? makeQueryClient());
  return (
    <QueryClientProvider client={queries}>
    <I18nProvider initialLang="en">
      <AuthProvider client={client}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
            <Route index element={<HomeRedirect />} />
            <Route path="queue" element={<RequireRole roles={["dispatcher"]}><QueuePage /></RequireRole>} />
            <Route path="incidents/:incidentId" element={<RequireRole roles={["dispatcher"]}><IncidentPage /></RequireRole>} />
            <Route path="admin" element={<RequireRole roles={["admin"]}><AdminPage /></RequireRole>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </I18nProvider>
    </QueryClientProvider>
  );
}

export function App({ client }: { client: ApiClient }) {
  return (
    <BrowserRouter>
      <Root client={client} />
    </BrowserRouter>
  );
}
