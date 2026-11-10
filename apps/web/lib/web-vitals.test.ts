import { afterEach, describe, expect, it, vi } from "vitest";
import { routeTemplate, sendVital, toVitalPayload, type VitalPayload } from "@/lib/web-vitals";

const UUID = "1b4e28ba-2fa1-11d2-883f-0016d3cca427";

const PAYLOAD: VitalPayload = {
  name: "INP",
  value: 184,
  rating: "good",
  id: "v5-1",
  navigation_type: "navigate",
  route: "/reports/[id]",
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("routeTemplate", () => {
  it("replaces uuid segments with [id]", () => {
    expect(routeTemplate(`/reports/${UUID}`)).toBe("/reports/[id]");
  });

  it("keeps routes without ids", () => {
    expect(routeTemplate("/sources")).toBe("/sources");
    expect(routeTemplate("/")).toBe("/");
  });

  it("drops the query and the hash", () => {
    expect(routeTemplate(`/reports/${UUID}?x=1#top`)).toBe("/reports/[id]");
  });
});

describe("toVitalPayload", () => {
  it("keeps only what the API accepts, with the route template", () => {
    const metric = {
      name: "INP",
      value: 184,
      rating: "good",
      id: "v5-1",
      navigationType: "navigate",
      delta: 12,
      entries: [],
    };
    expect(toVitalPayload(metric, `/reports/${UUID}`)).toEqual(PAYLOAD);
  });
});

describe("sendVital", () => {
  it("uses sendBeacon with a text/plain blob", async () => {
    const beacon = vi.fn().mockReturnValue(true);
    vi.stubGlobal("navigator", { sendBeacon: beacon });

    sendVital(PAYLOAD);

    expect(beacon).toHaveBeenCalledTimes(1);
    const [url, blob] = beacon.mock.calls[0] as [string, Blob];
    expect(url).toBe("http://localhost:8000/vitals");
    expect(blob.type).toBe("text/plain");
    expect(JSON.parse(await blob.text())).toEqual(PAYLOAD);
  });

  it("falls back to a keepalive fetch when sendBeacon refuses", () => {
    vi.stubGlobal("navigator", { sendBeacon: vi.fn().mockReturnValue(false) });
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    sendVital(PAYLOAD);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/vitals",
      expect.objectContaining({ method: "POST", keepalive: true, body: JSON.stringify(PAYLOAD) }),
    );
  });

  it("never throws when the network fails", () => {
    vi.stubGlobal("navigator", {});
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    expect(() => sendVital(PAYLOAD)).not.toThrow();
  });
});
