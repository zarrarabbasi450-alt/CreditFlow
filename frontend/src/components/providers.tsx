"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { AuthProvider } from "@/store/auth";
import { ToastProvider } from "@/components/toast";
import { useGatewayHealth } from "@/hooks/useGatewayHealth";

function GatewayProbe() {
  useGatewayHealth();
  return null;
}
function MockBoundary({ children }: { children: React.ReactNode }) {
  const mocksEnabled =
    process.env.NEXT_PUBLIC_ENV !== "production" && process.env.NEXT_PUBLIC_ENABLE_MOCKS !== "false";
  const [ready, setReady] = useState(!mocksEnabled);
  useEffect(() => {
    if (!mocksEnabled) return;
    import("@/mocks/browser")
      .then(({ worker }) => worker.start({ onUnhandledRequest: "bypass" }))
      .then(() => setReady(true));
  }, [mocksEnabled]);
  return ready ? children : <div className="loading-screen">Preparing your workspace…</div>;
}
export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30000, retry: 1, refetchOnWindowFocus: false },
          mutations: { retry: 0 },
        },
      }),
  );
  return (
    <MockBoundary>
      <QueryClientProvider client={client}>
        <AuthProvider>
          <GatewayProbe />
          <ToastProvider>{children}</ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </MockBoundary>
  );
}
