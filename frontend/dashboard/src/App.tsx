// Dispatcher and admin dashboard (B1-A3-01 shell, B1-A3-04 sign-in and role routing).
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ApiClient, I18nProvider } from "@amceds/shared";
import { AuthProvider } from "./auth/AuthProvider";
import { HomeRedirect, RequireAuth, RequireRole } from "./auth/guards";
import { AppLayout } from "./layout/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { AdminPage, QueuePage } from "./pages/placeholders";

/** Providers and routes; the router itself is chosen by the caller (browser, or memory in tests). */
export function Root({ client }: { client: ApiClient }) {
  return (
    <I18nProvider initialLang="en">
      <AuthProvider client={client}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
            <Route index element={<HomeRedirect />} />
            <Route path="queue" element={<RequireRole roles={["dispatcher"]}><QueuePage /></RequireRole>} />
            <Route path="admin" element={<RequireRole roles={["admin"]}><AdminPage /></RequireRole>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </I18nProvider>
  );
}

export function App({ client }: { client: ApiClient }) {
  return (
    <BrowserRouter>
      <Root client={client} />
    </BrowserRouter>
  );
}
