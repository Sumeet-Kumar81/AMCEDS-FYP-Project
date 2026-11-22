// Loading / empty / error states and the service banner.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/errors";
import { EmptyState, ErrorState, LoadingState, ServiceStatusBanner } from "./states";

describe("states", () => {
  it("loading and empty have default text", () => {
    render(<><LoadingState /><EmptyState /></>);
    expect(screen.getByRole("status")).toHaveTextContent("Loading…");
    expect(screen.getByText("Nothing to show yet.")).toBeInTheDocument();
  });

  it("an error shows our own words for known codes and a retry button", async () => {
    const retry = vi.fn();
    render(<ErrorState error={new ApiError(0, "network_error", "x")} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Could not reach the server. Check the connection.");
    expect(screen.getByRole("alert")).toHaveTextContent("(network_error)");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("a 503 tells the caller to phone 1122", () => {
    render(<ErrorState error={new ApiError(503, "service_unavailable", "Not saved.")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("call 1122 now");
  });

  it("a 501 says the part is not built, never success", () => {
    render(<ErrorState error={new ApiError(501, "not_implemented", "x", { task: "B1-A1-20" })} />);
    expect(screen.getByRole("alert")).toHaveTextContent("This part is not built yet (B1-A1-20).");
  });

  it("other errors show the server's message", () => {
    render(<ErrorState error={new ApiError(403, "forbidden", "Your role may not do this.")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Your role may not do this.");
  });
});

describe("ServiceStatusBanner", () => {
  it("is hidden when everything works", () => {
    const { container } = render(<ServiceStatusBanner services={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("names the services that are down and says manual work continues", () => {
    render(<ServiceStatusBanner services={["database"]} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Some services are not working: database.");
    expect(screen.getByRole("alert")).toHaveTextContent("Reports can still be handled by hand.");
  });

  it("warns when the server cannot be reached", () => {
    render(<ServiceStatusBanner services={[]} unreachable />);
    expect(screen.getByRole("alert")).toHaveTextContent("Cannot reach the server.");
  });
});
