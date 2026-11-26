import { chmod, mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { PNG } from "pngjs";
import { afterEach, describe, expect, it, vi } from "vitest";

import { sha256 } from "../src/crypto.js";
import { pillowDirectImageInspector } from "../src/direct-image-inspection.js";
import { ProjectDirectImageStore } from "../src/direct-image-store.js";
import { acquireDirectImage, type DirectImageIntent } from "../src/direct-image.js";
import { CaptureDenied, inspectPublicUrl, type TransportResponse } from "../src/policy.js";

const intent: DirectImageIntent = {
  projectId: "project-a",
  principal: { principalKind: "user", principalId: "editor-a" },
  documentRevisionId: "revision-a",
  occurrenceId: "occurrence-a",
  approvedUrl: "https://image.example/private-path?size=private-value",
};
const png = PNG.sync.write(new PNG({ width: 2, height: 3 }));
// A synthetic 2 × 3 JPEG generated with Pillow.
const jpeg = Buffer.from(
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a" +
  "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy" +
  "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAADAAIDASIA" +
  "AhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAj/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEB" +
  "AAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AJ/AB//Z",
  "base64",
);
const decoded = { mimeType: "image/png", width: 2, height: 3, orientation: 1, frameCount: 1 };
const ip = "93.184.216.34";
const response: TransportResponse = {
  status: 200, headers: { "content-type": "image/png" }, body: png, remoteAddress: ip,
  tls: { availability: "not_applicable", protocol: null, cipher: null, peerCertificateSha256: null, unavailableReason: null },
};
const roots: string[] = [];

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
});

async function fixture() {
  const root = await mkdtemp(join(tmpdir(), "vera-direct-image-"));
  roots.push(root);
  const source = join(root, sha256(intent.projectId).slice(7),
    sha256(inspectPublicUrl(intent.approvedUrl).canonicalUrl).slice(7));
  return {
    root, source,
    original: join(source, "original"),
    options: {
      authorizeEdit: vi.fn((input: DirectImageIntent) => Promise.resolve(input.documentRevisionId === intent.documentRevisionId)),
      inspector: { profile: "fixture/v1", inspect: vi.fn(() => Promise.resolve(decoded)) },
      resolver: { resolve: vi.fn(() => Promise.resolve([{ family: 4 as const, address: ip }])) },
      transport: { request: vi.fn(() => Promise.resolve(response)) },
      store: new ProjectDirectImageStore(root),
    },
  };
}

describe("trusted direct-image acquisition", () => {
  it("saves the exact original and reuses it after reopening, separately for each project", async () => {
    const { root, original, options } = await fixture();
    expect(await acquireDirectImage(intent, options)).toMatchObject({ status: "ready", buildQualification: "unqualified" });
    expect(await readFile(join(original, "image"))).toEqual(png);
    const receiptText = await readFile(join(original, "receipt.json"), "utf8");
    expect(receiptText).not.toContain("private");
    const receipt = JSON.parse(receiptText) as Record<string, unknown>;
    expect(receipt).toMatchObject({ ...decoded, contentHash: sha256(png), requestedOrigin: "https://image.example" });
    const reopened = { ...options, store: new ProjectDirectImageStore(root) };
    const reused = await acquireDirectImage({ ...intent, occurrenceId: "different-occurrence" }, reopened);
    expect(reused).toEqual({
      status: "reused", mediaReferenceId: receipt.mediaReferenceId, buildQualification: "unqualified",
    });
    expect(options.transport.request).toHaveBeenCalledTimes(1);
    expect(options.inspector.inspect).toHaveBeenCalledTimes(1);
    expect(await acquireDirectImage({ ...intent, projectId: "project-b" }, reopened)).toMatchObject({ status: "ready" });
    expect(options.transport.request).toHaveBeenCalledTimes(2);
  });

  it("requires current authority before any fetch or reuse and again before publish", async () => {
    const { root, source, options } = await fixture();
    expect(await acquireDirectImage({ ...intent, documentRevisionId: "stale" }, options)).toMatchObject({ status: "denied" });
    expect(await readdir(root)).toEqual([]);
    expect(options.transport.request).not.toHaveBeenCalled();
    options.authorizeEdit.mockResolvedValueOnce(true).mockResolvedValueOnce(true).mockResolvedValueOnce(false);
    expect(await acquireDirectImage(intent, options)).toMatchObject({ status: "denied" });
    expect(await readdir(source)).toEqual([]);
    expect(await acquireDirectImage(intent, options)).toMatchObject({ status: "ready" });
    options.authorizeEdit.mockResolvedValueOnce(true).mockResolvedValueOnce(false);
    expect(await acquireDirectImage(intent, options)).toMatchObject({ status: "denied" });
    expect(options.transport.request).toHaveBeenCalledTimes(2);
  });

  it("requires the matching recorded attempt for a retry and never repeats a successful retry", async () => {
    const { root, options } = await fixture();
    options.transport.request.mockResolvedValueOnce({ ...response, status: 503 });
    const failed = await acquireDirectImage(intent, options);
    expect(failed).toMatchObject({ status: "retryable", code: "image_http_status" });
    if (!("attemptId" in failed)) throw new Error("missing retry attempt");
    const reopened = { ...options, store: new ProjectDirectImageStore(root) };
    expect(await acquireDirectImage(intent, reopened)).toEqual(failed);
    expect(await acquireDirectImage({ ...intent, retryAttemptId: "wrong" }, reopened)).toEqual(failed);
    expect(await acquireDirectImage({ ...intent, approvedUrl: "https://image.example/another", retryAttemptId: failed.attemptId }, reopened))
      .toMatchObject({ status: "refused", code: "unknown_retry_attempt" });
    expect(options.transport.request).toHaveBeenCalledTimes(1);
    const retry = { ...intent, retryAttemptId: failed.attemptId };
    expect(await acquireDirectImage(retry, reopened)).toMatchObject({ status: "ready" });
    expect(await acquireDirectImage(retry, reopened)).toMatchObject({ status: "reused" });
    expect(options.transport.request).toHaveBeenCalledTimes(2);
  });

  it("refuses mixed DNS, private redirects, and an unexpected peer before decoding", async () => {
    const mixed = await fixture();
    mixed.options.resolver.resolve.mockResolvedValueOnce([{ family: 4, address: ip }, { family: 4, address: "127.0.0.1" }]);
    expect(await acquireDirectImage(intent, mixed.options)).toMatchObject({ status: "refused", code: "dns_not_public" });
    expect(mixed.options.transport.request).not.toHaveBeenCalled();
    const redirect = await fixture();
    redirect.options.transport.request.mockResolvedValueOnce({ ...response, status: 302, headers: { location: "https://localhost/private" } });
    expect(await acquireDirectImage(intent, redirect.options)).toMatchObject({ status: "refused", code: "local_name_not_allowed" });
    expect(redirect.options.transport.request).toHaveBeenCalledTimes(1);
    const mismatch = await fixture();
    mismatch.options.transport.request.mockResolvedValueOnce({ ...response, remoteAddress: "8.8.8.8" });
    expect(await acquireDirectImage(intent, mismatch.options)).toMatchObject({ status: "refused", code: "peer_mismatch" });
    expect(mismatch.options.inspector.inspect).not.toHaveBeenCalled();
  });

  it.each([
    [{ ...response, body: Buffer.from("<html>no image</html>") }, "unsupported_image"],
    [{ ...response, headers: { "content-type": "text/html" } }, "image_type_mismatch"],
  ] as const)("refuses invalid image responses before decoding", async (invalid, code) => {
    const { options } = await fixture();
    options.transport.request.mockResolvedValueOnce(invalid);
    const result = await acquireDirectImage(intent, options);
    expect(result).toMatchObject({ status: "refused", code });
    expect(options.inspector.inspect).not.toHaveBeenCalled();
    expect(await acquireDirectImage(intent, options)).toEqual(result);
    expect(options.transport.request).toHaveBeenCalledTimes(1);
  });

  it("distinguishes a timeout from a response that exceeds the size limit", async () => {
    const timeout = await fixture();
    timeout.options.transport.request.mockRejectedValueOnce(new CaptureDenied("connection_timeout", "fixture", "connect"));
    expect(await acquireDirectImage(intent, timeout.options)).toMatchObject({ status: "retryable", code: "connection_timeout" });
    const oversized = await fixture();
    oversized.options.transport.request.mockResolvedValueOnce({ ...response, body: Buffer.alloc(56 * 1024 * 1024 + 1) });
    expect(await acquireDirectImage(intent, oversized.options)).toMatchObject({ status: "refused", code: "response_too_large" });
    expect(oversized.options.inspector.inspect).not.toHaveBeenCalled();
  });

  it("serializes concurrent intake and preserves an incomplete attempt for inspection", async () => {
    const { source, options } = await fixture();
    let transportEntered!: () => void;
    let finish!: (value: TransportResponse) => void;
    const entered = new Promise<void>((resolve) => { transportEntered = resolve; });
    options.transport.request.mockImplementationOnce(() => new Promise((resolve) => {
      finish = resolve;
      transportEntered();
    }));
    const first = acquireDirectImage(intent, options);
    await entered;
    expect(await acquireDirectImage(intent, options)).toMatchObject({ status: "needs_inspection" });
    finish(response);
    expect(await first).toMatchObject({ status: "ready" });
    expect(await acquireDirectImage(intent, options)).toMatchObject({ status: "reused" });
    expect(options.transport.request).toHaveBeenCalledTimes(1);

    await rm(join(source, "original"), { recursive: true });
    expect(await acquireDirectImage(intent, options)).toMatchObject({ status: "needs_inspection" });
    expect(options.transport.request).toHaveBeenCalledTimes(1);
  });

  it("preserves an incomplete first attempt across reopen", async () => {
    const { root, source, options } = await fixture();
    await mkdir(source, { recursive: true, mode: 0o700 });
    await chmod(join(root, sha256(intent.projectId).slice(7)), 0o700);
    await mkdir(join(source, "pending"), { mode: 0o700 });
    expect(await acquireDirectImage(intent, options)).toMatchObject({ status: "needs_inspection" });
    expect(options.transport.request).not.toHaveBeenCalled();
  });

  it.each(["modified_original", "modified_receipt", "symlink", "public_permissions"] as const)(
    "does not fetch over storage tampering: %s", async (method) => {
      const { original, options } = await fixture();
      expect(await acquireDirectImage(intent, options)).toMatchObject({ status: "ready" });
      const image = join(original, "image");
      if (method === "modified_original") {
        const modified = Buffer.from(png);
        modified[modified.length - 1] = modified.at(-1)! ^ 1;
        await writeFile(image, modified);
      } else if (method === "modified_receipt") {
        const receipt = join(original, "receipt.json");
        await writeFile(receipt, (await readFile(receipt, "utf8")).replace('"width":2', '"width":3'));
      } else if (method === "symlink") {
        await rm(image);
        await symlink(join(original, "receipt.json"), image);
      } else {
        await chmod(image, 0o644);
      }
      expect(await acquireDirectImage(intent, options)).toMatchObject({ status: "needs_inspection" });
      expect(options.transport.request).toHaveBeenCalledTimes(1);
    },
  );

  const python = process.env.VERA_TEST_IMAGE_PYTHON;
  it.skipIf(!python).each(["image/png", "image/jpeg"])(
    "runs the real local inspector through intake and reopen for %s", async (mimeType) => {
      const { original, root, options } = await fixture();
      const real = { ...options, inspector: pillowDirectImageInspector(python!) };
      const body = mimeType === "image/png" ? png : jpeg;
      options.transport.request.mockResolvedValue({ ...response, headers: { "content-type": mimeType }, body });
      expect(await acquireDirectImage(intent, real)).toMatchObject({ status: "ready" });
      expect(JSON.parse(await readFile(join(original, "receipt.json"), "utf8"))).toMatchObject({ ...decoded, mimeType });
      expect(await readFile(join(original, "image"))).toEqual(body);
      expect(await acquireDirectImage(intent, { ...real, store: new ProjectDirectImageStore(root) }))
        .toMatchObject({ status: "reused" });
      expect(options.transport.request).toHaveBeenCalledTimes(1);
    },
  );
});
