import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/features/auth/login-form";
import { renderWithProviders } from "./test-providers";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
describe("LoginForm", () => {
  it("shows validation errors for invalid credentials", async () => {
    renderWithProviders(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/work email/i), { target: { value: "wrong" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(2));
  });
});
