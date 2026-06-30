import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import Index from "@/pages/Index";

const renderLanding = () =>
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/"]}>
        <Index />
      </MemoryRouter>
    </AuthProvider>,
  );

describe("landing page", () => {
  it("renders the hero headline and primary CTA", () => {
    renderLanding();
    expect(
      screen.getByRole("heading", { level: 1, name: /payroll that knows what a mile is worth/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /start free trial/i }).length).toBeGreaterThan(0);
  });

  it("renders the core sections", () => {
    renderLanding();
    expect(screen.getByText(/settlements your drivers stop calling about/i)).toBeInTheDocument();
    expect(screen.getByText(/the back office, handled/i)).toBeInTheDocument();
    expect(screen.getByText(/why carriers switch from generic payroll/i)).toBeInTheDocument();
    expect(screen.getByText(/priced for fleets, not tech budgets/i)).toBeInTheDocument();
  });

  it("renders all three pricing plans", () => {
    renderLanding();
    expect(screen.getByText("Payroll Only")).toBeInTheDocument();
    expect(screen.getByText("Combo")).toBeInTheDocument();
    expect(screen.getByText("Bookkeeping Only")).toBeInTheDocument();
  });
});
