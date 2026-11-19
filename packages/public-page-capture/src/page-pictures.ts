import { randomUUID } from "node:crypto";

import type { CreateCaptureRequest, PrincipalRef } from "@vera/contracts";

import { sha256, stableUuid } from "./crypto.js";
import { inspectPublicUrl } from "./policy.js";
import { CAPTURE_PROFILE_V2 } from "./profile.js";
import type { CaptureService } from "./service.js";

type PictureService = Pick<CaptureService, "createCapture" | "requestCaptureJob">;
type PictureRegion = CreateCaptureRequest["regionIntent"];

/** Queue the article once, and a separate immutable observation for each passage.
 * The caller can poll the returned jobs or replay this request after the worker runs. */
export async function requestPublicPagePictures(
  service: PictureService,
  projectId: string,
  principal: PrincipalRef,
  url: string,
  passage?: { exact: string; prefix?: string; suffix?: string },
) {
  const { canonicalUrl } = inspectPublicUrl(url);
  async function request(regionIntent: PictureRegion) {
    const key = sha256(JSON.stringify([canonicalUrl, regionIntent])).slice(7);
    const { capture } = await service.createCapture({
      schemaVersion: "public-page-capture-api/v1", messageType: "create_capture",
      projectId, clientRequestId: randomUUID(), idempotencyKey: `page-picture-create-${key}`,
      requestedUrl: canonicalUrl, regionIntent, acquisitionPolicy: { kind: "now" },
      captureProfileId: CAPTURE_PROFILE_V2.profileId, captureProfileVersion: CAPTURE_PROFILE_V2.profileVersion,
    }, principal);
    // Replays recover the first job even after its commit increments the capture row version.
    const { job } = await service.requestCaptureJob({
      schemaVersion: "public-page-capture-api/v1", messageType: "request_capture_job",
      projectId, captureId: capture.captureId, clientRequestId: randomUUID(),
      idempotencyKey: `page-picture-job-${key}`, expectedCaptureRowVersion: 1,
      trigger: { kind: "now", commandId: stableUuid([capture.captureId, key]), selectionIntent: { kind: "none" } },
    }, principal);
    return job;
  }

  const top = await request({ kind: "full_viewport" });
  const quoted = passage && await request({ kind: "passage", exact: passage.exact,
    ...(passage.prefix === undefined ? {} : { prefix: passage.prefix }),
    ...(passage.suffix === undefined ? {} : { suffix: passage.suffix }),
  });
  return { top, passage: quoted ?? null };
}
