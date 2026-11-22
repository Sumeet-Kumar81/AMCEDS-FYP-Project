// Dashboard shell: shows the server state from GET /health and the service banner.
import { render, screen } from "@testing-library/react";
import { ApiClient } from "@amceds/shared";
import { describe, expect, it } from "vitest";
import { App } from "./App";

function clientAnswering(body: unknown, status = 200): ApiClient {
  const fetchFn = (async () => new Response(JSON.stringify(body), { status })) as typeof fetch;
  return new ApiClient({ baseUrl: "http://api.test", fetch: fetchFn });
}

describe("dashboard shell", () => {
  it("shows the title, the SIMULATED notice and a connected server", async () => {
    render(<App client={clientAnswering({ api: "ok", database: "ok" })} />);
    expect(screen.getByRole("heading", { name: "AMCEDS — Dispatcher Dashboard" })).toBeInTheDocument();
    expect(screen.getByText(/SIMULATED/)).toBeInTheDocument();
    expect(await screen.findByText(/Server connected/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("warns when the database is down", async () => {
    render(<App client={clientAnswering({ api: "ok", database: "down" })} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Some services are not working: database.");
    expect(screen.queryByText(/Server connected/)).not.toBeInTheDocument();
  });

  it("warns when the server cannot be reached", async () => {
    const fetchFn = (async () => { throw new TypeError("Failed to fetch"); }) as typeof fetch;
    render(<App client={new ApiClient({ baseUrl: "http://api.test", fetch: fetchFn })} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");
  });
});
