import { describe, expect, it } from "vitest";

import {
  CaptureDenied,
  PublicEgressGuard,
  classifyAddress,
  inspectPublicUrl,
  type DnsResolver,
  type PinnedTransport,
  type TransportRequest,
  type TransportResponse,
} from "../src/policy.js";

const publicV4 = "93.184.216.34";
const publicV6 = "2606:2800:220:1:248:1893:25c8:1946";

class FixtureResolver implements DnsResolver {
  constructor(
    private readonly answers: Readonly<Record<string, readonly string[]>>,
  ) {}

  resolve(host: string) {
    return Promise.resolve(
      (this.answers[host] ?? []).map((address) => ({
        address,
        family: classifyAddress(address).family,
      })),
    );
  }
}

class FixtureTransport implements PinnedTransport {
  readonly requests: TransportRequest[] = [];

  constructor(
    private readonly respond: (
      request: TransportRequest,
    ) => TransportResponse | Promise<TransportResponse>,
  ) {}

  async request(request: TransportRequest): Promise<TransportResponse> {
    this.requests.push(request);
    return this.respond(request);
  }
}

describe("public capture URL admission", () => {
  it("canonicalizes a plain public URL and redacts every query value", () => {
    const inspected = inspectPublicUrl(
      "https://Capture.Example.org:443/story?edition=public&lang=en#section",
    );

    expect(inspected.canonicalUrl).toBe(
      "https://capture.example.org/story?edition=public&lang=en",
    );
    expect(inspected.redactedUrl).toBe(
      "https://capture.example.org/story?edition=%5BREDACTED%5D&lang=%5BREDACTED%5D",
    );
    expect(inspected.queryKeys).toEqual(["edition", "lang"]);
  });

  it.each([
    ["ftp://capture.example.org/", "scheme_not_allowed"],
    ["https://capture.example.org:8443/", "port_not_allowed"],
    ["https://user:password@capture.example.org/", "userinfo_not_allowed"],
    ["https://capture.example.org/?TOKEN=value", "credential_shape_not_allowed"],
    ["https://localhost/", "local_name_not_allowed"],
    ["https://metadata.google.internal/", "local_name_not_allowed"],
    ["https://127.0.0.1/", "ip_literal_not_allowed"],
    ["http://2130706433/", "ip_literal_not_allowed"],
    ["https://[::1]/", "ip_literal_not_allowed"],
    ["https:\\capture.example.org\\story", "ambiguous_url"],
    ["https://capture.example.org/%00", "control_character"],
  ])("rejects %s as %s", (raw, code) => {
    expect(() => inspectPublicUrl(raw)).toThrowError(
      expect.objectContaining({ code }),
    );
  });
});

describe("IP classification", () => {
  it.each([
    ["0.0.0.0", "unspecified"],
    ["10.2.3.4", "private"],
    ["100.64.0.1", "private"],
    ["127.0.0.1", "loopback"],
    ["169.254.1.1", "link_local"],
    ["172.20.1.1", "private"],
    ["192.168.1.1", "private"],
    ["192.0.2.2", "reserved"],
    ["198.18.0.1", "reserved"],
    ["198.51.100.2", "reserved"],
    ["203.0.113.2", "reserved"],
    ["224.0.0.1", "multicast"],
    ["255.255.255.255", "reserved"],
    ["::", "unspecified"],
    ["::1", "loopback"],
    ["fc00::1", "private"],
    ["fe80::1", "link_local"],
    ["ff02::1", "multicast"],
    ["2001:db8::1", "reserved"],
    ["::ffff:127.0.0.1", "loopback"],
    [publicV4, "public"],
    [publicV6, "public"],
  ])("classifies %s as %s", (address, addressClass) => {
    expect(classifyAddress(address).addressClass).toBe(addressClass);
  });

  it("rejects malformed addresses", () => {
    expect(() => classifyAddress("not-an-address")).toThrow(CaptureDenied);
  });
});

describe("pinned public egress", () => {
  it("pins an admitted address and verifies the actual peer", async () => {
    const resolver = new FixtureResolver({
      "capture.example.org": [publicV4],
    });
    const transport = new FixtureTransport((request) => ({
      status: 200,
      headers: {
        "content-type": "text/html; charset=utf-8",
      },
      body: Buffer.from("<h1>fixture</h1>"),
      remoteAddress: request.pinnedAddress,
      tls: {
        availability: "available",
        protocol: "TLSv1.3",
        cipher: "fixture",
        peerCertificateSha256: null,
        unavailableReason: null,
      },
    }));
    const guard = new PublicEgressGuard(resolver, transport);

    const response = await guard.fetch(
      "https://capture.example.org/story?edition=public",
    );

    expect(response.status).toBe(200);
    expect(response.body.toString()).toContain("fixture");
    expect(response.trace.actualConnectionCount).toBe(1);
    expect(transport.requests[0]).toMatchObject({
      host: "capture.example.org",
      port: 443,
      pinnedAddress: publicV4,
      method: "GET",
    });
    expect(transport.requests[0]?.headers).toEqual({
      accept: "text/html,application/xhtml+xml,image/*;q=0.8,*/*;q=0.5",
      "user-agent": "VERA Public Page Capture/1",
    });
  });

  it("rejects an empty, nonpublic, or mixed DNS answer set before transport", async () => {
    for (const answers of [
      [],
      ["127.0.0.1"],
      [publicV4, "10.0.0.1"],
      [publicV6, "fe80::1"],
    ]) {
      const transport = new FixtureTransport(() => {
        throw new Error("transport must not run");
      });
      const guard = new PublicEgressGuard(
        new FixtureResolver({ "capture.example.org": answers }),
        transport,
      );

      await expect(
        guard.fetch("https://capture.example.org/"),
      ).rejects.toMatchObject({
        code: answers.length === 0 ? "dns_no_answers" : "dns_not_public",
        navigationStarted: false,
      });
      expect(transport.requests).toHaveLength(0);
    }
  });

  it("rejects a peer that differs from the pinned address", async () => {
    const guard = new PublicEgressGuard(
      new FixtureResolver({ "capture.example.org": [publicV4] }),
      new FixtureTransport(() => ({
        status: 200,
        headers: {},
        body: Buffer.from("unexpected"),
        remoteAddress: "93.184.216.35",
        tls: {
          availability: "unavailable",
          protocol: null,
          cipher: null,
          peerCertificateSha256: null,
          unavailableReason: "fixture",
        },
      })),
    );

    await expect(
      guard.fetch("https://capture.example.org/"),
    ).rejects.toMatchObject({
      code: "peer_mismatch",
      navigationStarted: false,
    });
  });

  it("revalidates every redirect destination", async () => {
    const transport = new FixtureTransport((request) => ({
      status: 302,
      headers: { location: "http://redirect.example.org/private" },
      body: Buffer.alloc(0),
      remoteAddress: request.pinnedAddress,
      tls: {
        availability: "available",
        protocol: "TLSv1.3",
        cipher: "fixture",
        peerCertificateSha256: null,
        unavailableReason: null,
      },
    }));
    const guard = new PublicEgressGuard(
      new FixtureResolver({
        "capture.example.org": [publicV4],
        "redirect.example.org": ["10.0.0.7"],
      }),
      transport,
    );

    await expect(
      guard.fetch("https://capture.example.org/"),
    ).rejects.toMatchObject({
      code: "dns_not_public",
      phase: "dns",
    });
    expect(transport.requests).toHaveLength(1);
  });

  it("enforces redirect and byte limits without opening a fallback path", async () => {
    const resolver = new FixtureResolver({
      "capture.example.org": [publicV4],
    });
    const redirecting = new FixtureTransport((request) => ({
      status: 302,
      headers: { location: "/again" },
      body: Buffer.alloc(0),
      remoteAddress: request.pinnedAddress,
      tls: {
        availability: "available",
        protocol: "TLSv1.3",
        cipher: "fixture",
        peerCertificateSha256: null,
        unavailableReason: null,
      },
    }));
    await expect(
      new PublicEgressGuard(resolver, redirecting, {
        maxRedirects: 1,
      }).fetch("https://capture.example.org/"),
    ).rejects.toMatchObject({ code: "redirect_limit" });

    const oversized = new FixtureTransport((request) => ({
      status: 200,
      headers: {},
      body: Buffer.alloc(33),
      remoteAddress: request.pinnedAddress,
      tls: {
        availability: "available",
        protocol: "TLSv1.3",
        cipher: "fixture",
        peerCertificateSha256: null,
        unavailableReason: null,
      },
    }));
    await expect(
      new PublicEgressGuard(resolver, oversized, {
        maxResponseBytes: 32,
      }).fetch("https://capture.example.org/"),
    ).rejects.toMatchObject({ code: "response_too_large" });
  });
});
