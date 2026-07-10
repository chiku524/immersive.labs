import { describe, expect, it } from "vitest";
import { classifyJobFailure } from "../components/StudioJobFailurePanel";
import { isGatewayDetailMessage } from "../studio/studioApiHelpers";

describe("classifyJobFailure", () => {
  it("detects JSON parse failures", () => {
    const c = classifyJobFailure("No JSON object found in model output");
    expect(c.kind).toBe("json");
    expect(c.title).toMatch(/Spec generation/i);
  });

  it("detects gateway blips", () => {
    const c = classifyJobFailure("Gateway or tunnel returned HTTP 502 HTML instead of JSON");
    expect(c.kind).toBe("gateway");
  });

  it("detects Tripo key issues", () => {
    const c = classifyJobFailure("Tripo API key rejected (401) — check STUDIO_TRIPO_API_KEY");
    expect(c.kind).toBe("tripo");
  });
});

describe("isGatewayDetailMessage", () => {
  it("matches coerced edge errors", () => {
    expect(isGatewayDetailMessage("Gateway or tunnel returned HTTP 502")).toBe(true);
    expect(isGatewayDetailMessage("No JSON object found")).toBe(false);
  });
});
