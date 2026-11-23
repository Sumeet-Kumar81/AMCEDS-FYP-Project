// Report page behaviour (B1-A3-03): TC-01 (reference after save), D-036 (place, name, 03-phone required), TC-04 (safe resend),
// TC-47 (1122 notice), GPS paths, error states, Urdu. Fake fetch and fake geolocation; no network.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiClient } from "@amceds/shared";
import { describe, expect, it } from "vitest";
import { App } from "../App";

type Reply = Response | Error | (() => Promise<Response>);

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status });
}

const SAVED = { reference_no: "INC-000042", status: "new", received_at: "2026-11-22T08:32:38Z" };
const HEALTHY = { api: "ok", database: "ok" };

/** A client whose /health is fine and whose POST /reports answers come from `replies`, in order. */
function fakeApi(replies: Reply[]) {
  const posts: Record<string, unknown>[] = [];
  const fetchFn = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input);
    if (url.endsWith("/health")) return json(200, HEALTHY);
    posts.push(JSON.parse(String(init.body)));
    const reply = replies.shift() ?? json(500, { code: "test", message: "no reply left" });
    if (reply instanceof Error) throw reply;
    if (typeof reply === "function") return reply();
    return reply;
  }) as typeof fetch;
  return { client: new ApiClient({ baseUrl: "http://api.test", fetch: fetchFn }), posts };
}

function fakeGeo(result: { lat: number; lon: number; accuracy: number } | { code: number }) {
  return {
    getCurrentPosition: (ok: PositionCallback, fail?: PositionErrorCallback | null) => {
      if ("code" in result) fail?.({ code: result.code, message: "SIMULATED", PERMISSION_DENIED: 1,
        POSITION_UNAVAILABLE: 2, TIMEOUT: 3 } as GeolocationPositionError);
      else ok({ coords: { latitude: result.lat, longitude: result.lon, accuracy: result.accuracy } } as GeolocationPosition);
    },
  } as unknown as Geolocation;
}

const box = (id: string) => document.getElementById(id) as HTMLInputElement; // by id: works in English and Urdu

/** D-036: place, name and phone are required — fill the ones still empty with SIMULATED values. */
async function fillRequired(user: ReturnType<typeof userEvent.setup>) {
  if (!box("rf-address").value) await user.type(box("rf-address"), "near Clock Tower");
  if (!box("rf-name").value) await user.type(box("rf-name"), "SIMULATED Ali");
  if (!box("rf-phone").value) await user.type(box("rf-phone"), "03001234567");
}

async function fillAndSend(user: ReturnType<typeof userEvent.setup>, text = "SIMULATED: bus accident, 3 people hurt") {
  await fillRequired(user);
  await user.type(screen.getByLabelText(/What happened\?/), text);
  await user.click(screen.getByRole("button", { name: "Send report" }));
}

describe("sending a report", () => {
  it("shows the reference number only after the server saved it (TC-01)", async () => {
    const { client, posts } = fakeApi([json(201, SAVED)]);
    const user = userEvent.setup();
    render(<App client={client} geolocation={fakeGeo({ code: 2 })} />);
    expect(screen.queryByTestId("reference-no")).not.toBeInTheDocument();
    await fillAndSend(user);
    expect(await screen.findByTestId("reference-no")).toHaveTextContent("INC-000042");
    expect(screen.getByText(/is in the dispatcher's queue/)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("also call 1122"); // TC-47 after sending too
    expect(posts).toHaveLength(1);
    expect(posts[0]).toMatchObject({ description: "SIMULATED: bus accident, 3 people hurt", channel: "web" });
    expect(posts[0]!.client_request_id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("D-036: without place, name or phone nothing is sent and each field says why", async () => {
    const { client, posts } = fakeApi([]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await user.type(screen.getByLabelText(/What happened\?/), "SIMULATED: fire");
    await user.click(screen.getByRole("button", { name: "Send report" }));
    expect(screen.getByText("Please type the place or a landmark.")).toBeInTheDocument();
    expect(screen.getByText("Please write your name.")).toBeInTheDocument();
    expect(screen.getByText("Please write your phone number.")).toBeInTheDocument();
    expect(box("rf-address")).toHaveFocus();
    expect(posts).toHaveLength(0);
  });

  it("without GPS the typed place is sent and no coordinates", async () => {
    const { client, posts } = fakeApi([json(201, SAVED)]);
    const user = userEvent.setup();
    render(<App client={client} geolocation={fakeGeo({ code: 1 })} />);
    await fillAndSend(user);
    await screen.findByTestId("reference-no");
    expect(posts[0]).not.toHaveProperty("lat");
    expect(posts[0]).toMatchObject({ address_text: "near Clock Tower", reporter_name: "SIMULATED Ali", reporter_phone: "03001234567" });
  });

  it("D-036: the place, name and phone are marked as required", () => {
    render(<App client={fakeApi([]).client} />);
    expect(screen.getByText(/Place or landmark/).textContent).toContain("(required)");
    expect(screen.getByText("Your details").textContent).toContain("(required)");
    expect(screen.queryByText("(optional)")).not.toBeInTheDocument();
  });

  it("an empty report is not sent", async () => {
    const { client, posts } = fakeApi([]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await user.click(screen.getByRole("button", { name: "Send report" }));
    expect(screen.getByText("Please describe what happened.")).toBeInTheDocument();
    expect(screen.getByLabelText(/What happened\?/)).toHaveFocus();
    expect(posts).toHaveLength(0);
  });

  it("a wrong phone number is caught before sending", async () => {
    const { client, posts } = fakeApi([]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await user.type(screen.getByLabelText("Phone number"), "abc");
    await fillAndSend(user);
    expect(screen.getByText(/Phone must be 11 digits starting with 03/)).toBeInTheDocument();
    expect(screen.getByLabelText("Phone number")).toHaveAttribute("aria-invalid", "true");
    expect(posts).toHaveLength(0);
  });

  it.each(["04001234567", "0300123456", "030012345678", "+923001234567"])("D-036: phone %s is refused", async (phone) => {
    const { client, posts } = fakeApi([]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await user.type(screen.getByLabelText("Phone number"), phone);
    await fillAndSend(user);
    expect(screen.getByText(/Phone must be 11 digits starting with 03/)).toBeInTheDocument();
    expect(posts).toHaveLength(0);
  });

  it("D-036: a phone typed with spaces or dashes is sent as 11 digits", async () => {
    const { client, posts } = fakeApi([json(201, SAVED)]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await user.type(screen.getByLabelText("Phone number"), "0300 123-4567");
    await fillAndSend(user);
    await screen.findByTestId("reference-no");
    expect(posts[0]).toMatchObject({ reporter_phone: "03001234567" });
  });

  it("a double press sends one request", async () => {
    let release!: (r: Response) => void;
    const slow = () => new Promise<Response>((resolve) => { release = resolve; });
    const { client, posts } = fakeApi([slow]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await fillRequired(user);
    await user.type(screen.getByLabelText(/What happened\?/), "SIMULATED: fire");
    const send = screen.getByRole("button", { name: "Send report" });
    await user.click(send);
    await user.click(screen.getByRole("button", { name: "Sending…" }));
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
    await act(async () => release(json(201, SAVED)));
    await screen.findByTestId("reference-no");
    expect(posts).toHaveLength(1);
  });
  it("two submits in the same moment (Enter pressed twice) send one request", async () => {
    let release!: (r: Response) => void;
    const { client, posts } = fakeApi([() => new Promise<Response>((resolve) => { release = resolve; })]);
    render(<App client={client} />);
    fireEvent.change(screen.getByLabelText(/What happened\?/), { target: { value: "SIMULATED: fire" } });
    fireEvent.change(box("rf-address"), { target: { value: "near Clock Tower" } });
    fireEvent.change(box("rf-name"), { target: { value: "SIMULATED Ali" } });
    fireEvent.change(box("rf-phone"), { target: { value: "03001234567" } });
    const form = screen.getByRole("button", { name: "Send report" }).closest("form")!;
    act(() => {
      fireEvent.submit(form);
      fireEvent.submit(form); // before React re-renders the disabled button
    });
    await act(async () => release(json(201, SAVED)));
    await screen.findByTestId("reference-no");
    expect(posts).toHaveLength(1);
  });
});

describe("resending safely (TC-04)", () => {
  it("after a lost answer, Send again uses the same id; a 200 shows the same reference", async () => {
    const { client, posts } = fakeApi([new TypeError("Failed to fetch"), json(200, SAVED)]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await fillAndSend(user);
    expect(await screen.findByText(/Your report was not sent: no connection/)).toBeInTheDocument();
    expect(screen.queryByTestId("reference-no")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByTestId("reference-no")).toHaveTextContent("INC-000042");
    expect(screen.getByText(/had already reached us/)).toBeInTheDocument();
    expect(posts).toHaveLength(2);
    expect(posts[1]!.client_request_id).toBe(posts[0]!.client_request_id);
  });

  it("an edited report after a failure gets a new id", async () => {
    const { client, posts } = fakeApi([new TypeError("Failed to fetch"), json(201, SAVED)]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await fillAndSend(user);
    await screen.findByText(/no connection/);
    await user.type(screen.getByLabelText(/What happened\?/), " and a fire");
    await user.click(screen.getByRole("button", { name: "Send report" }));
    await screen.findByTestId("reference-no");
    expect(posts[1]!.client_request_id).not.toBe(posts[0]!.client_request_id);
  });

  it("a new report after success starts empty with a new id", async () => {
    const { client, posts } = fakeApi([json(201, SAVED), json(201, { ...SAVED, reference_no: "INC-000043" })]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await fillAndSend(user);
    await user.click(await screen.findByRole("button", { name: "Send another report" }));
    expect(screen.getByLabelText(/What happened\?/)).toHaveValue("");
    await fillAndSend(user);
    expect(await screen.findByTestId("reference-no")).toHaveTextContent("INC-000043");
    expect(posts[1]!.client_request_id).not.toBe(posts[0]!.client_request_id);
  });
});

describe("errors never show a reference number", () => {
  it("503: not saved, call 1122 now; the text is kept for another try", async () => {
    const { client } = fakeApi([json(503, { code: "service_unavailable", message: "Not saved.", details: null })]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await fillAndSend(user);
    expect(await screen.findByText(/Your report was NOT saved\. If life is in danger, call 1122 now/)).toBeInTheDocument();
    expect(screen.queryByTestId("reference-no")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/What happened\?/)).toHaveValue("SIMULATED: bus accident, 3 people hurt");
  });

  it("422 from the server is shown under its field", async () => {
    const body = { code: "validation_error", message: "The request is not valid.",
      details: [{ loc: ["body", "address_text"], msg: "String should have at most 500 characters", type: "string_too_long" }] };
    const { client } = fakeApi([json(422, body)]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await fillAndSend(user);
    expect(await screen.findByText("String should have at most 500 characters")).toBeInTheDocument();
    expect(screen.getByText("Please correct the marked fields.")).toBeInTheDocument();
  });

  it("429: too many reports, call 1122", async () => {
    const { client } = fakeApi([json(429, { code: "too_many_requests", message: "Too many.", details: null })]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await fillAndSend(user);
    expect(await screen.findByText(/Too many reports from this device/)).toBeInTheDocument();
  });

  it("anything else names the code", async () => {
    const { client } = fakeApi([json(500, { code: "internal_error", message: "x", details: null })]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await fillAndSend(user);
    expect(await screen.findByText(/could not be sent \(internal_error\)/)).toBeInTheDocument();
  });
});

describe("location", () => {
  it("GPS is added, shown with its accuracy, sent, and can be removed", async () => {
    const { client, posts } = fakeApi([json(201, SAVED)]);
    const user = userEvent.setup();
    render(<App client={client} geolocation={fakeGeo({ lat: 27.7052, lon: 68.8574, accuracy: 12.4 })} />);
    await user.click(screen.getByRole("button", { name: /Use my location/ }));
    expect(screen.getByText(/accurate to about 12 m/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove my location" }));
    expect(screen.getByRole("button", { name: /Use my location/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Use my location/ }));
    await fillAndSend(user);
    await screen.findByTestId("reference-no");
    expect(posts[0]).toMatchObject({ lat: 27.7052, lon: 68.8574 });
  });

  it.each([
    [1, /permission was refused/],
    [2, /could not be found/],
    [3, /could not be found/],
  ])("GPS error %i asks for a place or landmark", async (code, message) => {
    const user = userEvent.setup();
    render(<App client={fakeApi([]).client} geolocation={fakeGeo({ code })} />);
    await user.click(screen.getByRole("button", { name: /Use my location/ }));
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.getByLabelText(/Place or landmark/)).toBeEnabled();
  });

  it("a browser without GPS says so", async () => {
    const user = userEvent.setup();
    const original = Object.getOwnPropertyDescriptor(navigator, "geolocation");
    Object.defineProperty(navigator, "geolocation", { value: undefined, configurable: true });
    try {
      render(<App client={fakeApi([]).client} />);
      await user.click(screen.getByRole("button", { name: /Use my location/ }));
      expect(screen.getByText(/cannot share a location/)).toBeInTheDocument();
    } finally {
      if (original) Object.defineProperty(navigator, "geolocation", original);
      else delete (navigator as { geolocation?: unknown }).geolocation;
    }
  });

  it("a typed landmark is sent as address_text", async () => {
    const { client, posts } = fakeApi([json(201, SAVED)]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await user.type(screen.getByLabelText(/Place or landmark/), "near Clock Tower");
    await fillAndSend(user);
    await screen.findByTestId("reference-no");
    expect(posts[0]).toMatchObject({ address_text: "near Clock Tower" });
  });
});

describe("page rules", () => {
  it("voice recording is shown as not available, never as working", () => {
    render(<App client={fakeApi([]).client} />);
    expect(screen.getByRole("button", { name: /Record voice \(coming soon\)/ })).toBeDisabled();
  });

  it("the 1122 notice stays visible while sending and on errors (TC-47)", async () => {
    let release!: (r: Response) => void;
    const { client } = fakeApi([() => new Promise<Response>((resolve) => { release = resolve; })]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await fillAndSend(user);
    expect(screen.getByRole("note")).toHaveTextContent("also call 1122");
    await act(async () => release(json(503, { code: "service_unavailable", message: "x", details: null })));
    await screen.findByText(/NOT saved/);
    expect(screen.getByRole("note")).toHaveTextContent("also call 1122");
  });

  it("works in Urdu: labels, button and direction", async () => {
    const { client, posts } = fakeApi([json(201, SAVED)]);
    const user = userEvent.setup();
    render(<App client={client} />);
    await user.click(screen.getByRole("button", { name: "اردو" }));
    expect(document.documentElement).toHaveAttribute("dir", "rtl");
    await fillRequired(user);
    await user.type(screen.getByLabelText(/کیا ہوا ہے؟/), "SIMULATED: مینارہ روڈ پر آگ لگ گئی ہے");
    await user.click(screen.getByRole("button", { name: "رپورٹ بھیجیں" }));
    expect(await screen.findByRole("heading", { name: /رپورٹ محفوظ ہو گئی/ })).toBeInTheDocument();
    await waitFor(() => expect(posts[0]).toMatchObject({ description: "SIMULATED: مینارہ روڈ پر آگ لگ گئی ہے" }));
  });

  it("the text boxes follow the writing direction of what is typed", () => {
    render(<App client={fakeApi([]).client} />);
    expect(screen.getByLabelText(/What happened\?/)).toHaveAttribute("dir", "auto");
    expect(screen.getByLabelText("Phone number")).toHaveAttribute("dir", "ltr");
  });
});
