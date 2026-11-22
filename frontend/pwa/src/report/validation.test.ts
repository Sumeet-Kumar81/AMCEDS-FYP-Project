// Report form rules mirror backend ReportIn; request body shape; server 422 mapping; submission ids.
import { describe, expect, it } from "vitest";
import {
  EMPTY_DRAFT,
  LIMITS,
  newRequestId,
  sameDraft,
  serverFieldErrors,
  toReportIn,
  validate,
  type ReportDraft,
} from "./validation";

const draft = (d: Partial<ReportDraft> = {}): ReportDraft => ({ ...EMPTY_DRAFT, description: "SIMULATED: fire", ...d });

describe("validate", () => {
  it("a description is the only required field", () => {
    expect(validate(draft())).toEqual({});
    expect(validate(draft({ description: "   " })).description?.key).toBe("report.err_description_required");
  });

  it("limits match the backend", () => {
    expect(validate(draft({ description: "x".repeat(LIMITS.description) }))).toEqual({});
    expect(validate(draft({ description: "x".repeat(LIMITS.description + 1) })).description?.key).toBe("report.err_too_long");
    expect(validate(draft({ addressText: "x".repeat(501) })).addressText?.vars).toEqual({ max: 500 });
    expect(validate(draft({ name: "x".repeat(101) })).name?.vars).toEqual({ max: 100 });
  });

  it.each(["0300 1234567", "+92-300-1234567", "03001234567"])("accepts phone %s", (phone) => {
    expect(validate(draft({ phone }))).toEqual({});
  });

  it.each(["abc", "12", "0300 12345x7", "+"])("refuses phone %s", (phone) => {
    expect(validate(draft({ phone })).phone?.key).toBe("report.err_phone");
  });

  it("accepts Urdu and Sindhi text", () => {
    expect(validate(draft({ description: "SIMULATED: مینارہ روڈ پر آگ لگ گئی ہے" }))).toEqual({});
    expect(validate(draft({ description: "SIMULATED: ڪراچي روڊ تي حادثو ٿيو آهي" }))).toEqual({});
  });
});

describe("toReportIn", () => {
  it("trims, leaves out empty optional fields and sends no coordinates without GPS", () => {
    expect(toReportIn(draft({ description: "  SIMULATED: fire  ", name: "  ", phone: "" }), "id-1")).toEqual({
      description: "SIMULATED: fire", channel: "web", client_request_id: "id-1" });
  });

  it("sends GPS coordinates and the typed place together", () => {
    const body = toReportIn(draft({ addressText: " near Clock Tower ", gps: { lat: 27.7, lon: 68.85, accuracy: 12 },
      name: "SIMULATED Ali", phone: "0300 1234567" }), "id-2");
    expect(body).toEqual({ description: "SIMULATED: fire", channel: "web", client_request_id: "id-2",
      address_text: "near Clock Tower", lat: 27.7, lon: 68.85, reporter_name: "SIMULATED Ali",
      reporter_phone: "0300 1234567" });
    expect(body).not.toHaveProperty("accuracy");
  });
});

describe("serverFieldErrors", () => {
  it("puts each server problem under its field", () => {
    const errors = serverFieldErrors([
      { loc: ["body", "reporter_phone"], msg: "String should match pattern", type: "string_pattern_mismatch" },
      { loc: ["body"], msg: "Value error, lat and lon must both be given or both be left out", type: "value_error" },
    ]);
    expect(errors.phone?.text).toBe("String should match pattern");
    expect(errors.location?.text).toBe("lat and lon must both be given or both be left out");
  });
});

describe("submission ids", () => {
  it("are UUIDs, also without crypto.randomUUID (plain-http LAN address)", () => {
    const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
    expect(newRequestId()).toMatch(uuid);
    const noRandomUuid = { getRandomValues: crypto.getRandomValues.bind(crypto) };
    expect(newRequestId(noRandomUuid)).toMatch(uuid);
    expect(newRequestId(noRandomUuid)).not.toBe(newRequestId(noRandomUuid));
  });

  it("a change in the report means a different report", () => {
    expect(sameDraft(draft({ name: "A " }), draft({ name: "A" }))).toBe(true);
    expect(sameDraft(draft(), draft({ description: "SIMULATED: flood" }))).toBe(false);
    expect(sameDraft(draft(), draft({ gps: { lat: 1, lon: 2, accuracy: 5 } }))).toBe(false);
  });
});
