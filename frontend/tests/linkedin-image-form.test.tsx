import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LinkedInImageForm } from "@/features/publishing/linkedin-image-form";
import { renderWithProviders } from "./test-providers";
describe("LinkedInImageForm", () => {
  it("requires a meaningful caption and supported image", async () => {
    renderWithProviders(<LinkedInImageForm />);
    fireEvent.change(screen.getByLabelText(/post caption/i), { target: { value: "Short" } });
    fireEvent.click(screen.getByRole("button", { name: /publish to linkedin/i }));
    await waitFor(() => {
      expect(screen.getByText(/caption must/i)).toBeInTheDocument();
      expect(screen.getByText(/select an image/i)).toBeInTheDocument();
    });
  });
});
