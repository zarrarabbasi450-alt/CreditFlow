import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RecurringScheduleForm } from "@/features/scheduler/recurring-form";
import { renderWithProviders } from "./test-providers";
describe("RecurringScheduleForm", () => {
  it("validates the title and first run", async () => {
    renderWithProviders(<RecurringScheduleForm />);
    fireEvent.click(screen.getByRole("button", { name: /create recurring/i }));
    await waitFor(() => {
      expect(screen.getByText(/title must/i)).toBeInTheDocument();
      expect(screen.getByText(/select a start/i)).toBeInTheDocument();
    });
  });
});
