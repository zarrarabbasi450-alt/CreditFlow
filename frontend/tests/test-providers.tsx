import { render } from "@testing-library/react";
import { AuthProvider } from "@/store/auth";
import { ToastProvider } from "@/components/toast";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
export function renderWithProviders(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <ToastProvider>{ui}</ToastProvider>
      </AuthProvider>
    </QueryClientProvider>,
  );
}
