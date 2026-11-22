// Report page shell: the 1122 notice is always visible (TC-47), in English and Urdu, even when the
// server cannot be reached.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiClient } from "@amceds/shared";
import { describe, expect, it } from "vitest";
import { App } from "./App";

const down = new ApiClient({
  baseUrl: "http://api.test",
  fetch: (async () => { throw new TypeError("Failed to fetch"); }) as typeof fetch,
});

describe("report page shell", () => {
  it("shows the 1122 notice before anything has loaded", () => {
    render(<App client={down} />);
    expect(screen.getByRole("note")).toHaveTextContent("If life is in danger, also call 1122.");
  });

  it("keeps the notice when the server is down", async () => {
    render(<App client={down} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");
    expect(screen.getByRole("note")).toBeInTheDocument();
  });

  it("switches to Urdu, right to left, with the notice in Urdu", async () => {
    render(<App client={down} />);
    await userEvent.click(screen.getByRole("button", { name: "اردو" }));
    expect(screen.getByRole("heading", { name: "ایمرجنسی رپورٹ" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("اگر جان کو خطرہ ہو تو 1122 پر بھی کال کریں۔");
    expect(document.documentElement).toHaveAttribute("dir", "rtl");
  });
});
