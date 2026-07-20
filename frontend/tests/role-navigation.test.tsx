import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RoleNavigation } from "@/components/role-navigation";
import { render } from "@testing-library/react";
vi.mock("next/navigation", () => ({ usePathname: () => "/dashboard" }));
describe("role navigation", () => {
  it("hides billing and operations from members", () => {
    render(<RoleNavigation role="Member" />);
    expect(screen.queryByText("Billing")).not.toBeInTheDocument();
    expect(screen.queryByText("Operations")).not.toBeInTheDocument();
  });
  it("shows platform operations only to SuperAdmin", () => {
    render(<RoleNavigation role="SuperAdmin" />);
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Billing")).toBeInTheDocument();
  });
});
