import { createHash, randomUUID } from "node:crypto";
import { link, mkdir, open, unlink, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ResearchQuotePictureV2 } from "@vera/contracts/v2";

function retainedPath(picture: ResearchQuotePictureV2, home: string) {
  const { original, researchProjectId, revisionId } = picture;
  const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/u;
  if (!uuid.test(researchProjectId) || !uuid.test(revisionId) || !/^[a-f0-9]{64}$/u.test(original.sha256) ||
      !Number.isSafeInteger(original.byteCount) || original.byteCount < 1 || original.byteCount > 20 * 1024 * 1024) {
    throw new Error("Invalid retained quote picture.");
  }
  const root = join(home, ".local", "state", "vera", "research-quote-pictures");
  const directory = join(root, researchProjectId, revisionId);
  return { directory, file: join(directory, original.sha256) };
}

/** Preserve an exact kept revision for Prep Media, including after a Research picture is replaced. */
export async function retainResearchQuotePicture(
  picture: ResearchQuotePictureV2, bytes: Uint8Array, home = homedir(),
): Promise<void> {
  const { directory, file } = retainedPath(picture, home);
  if (!matches(bytes, picture)) throw new Error("Invalid retained quote picture.");
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const staging = join(directory, `.${randomUUID()}`);
  await writeFile(staging, bytes, { flag: "wx", mode: 0o600 });
  try {
    await link(staging, file);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
    // Atomic publication means an existing object must already be complete.
    if (!await readRetainedResearchQuotePicture(picture, home)) {
      throw new Error("Retained quote picture differs from its pin.", { cause: error });
    }
  } finally {
    await unlink(staging);
  }
}

export async function readRetainedResearchQuotePicture(picture: ResearchQuotePictureV2, home = homedir()) {
  const { file } = retainedPath(picture, home);
  try {
    const saved = await open(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    try {
      const stat = await saved.stat();
      if (!stat.isFile() || stat.size !== picture.original.byteCount) return null;
      const bytes = Buffer.alloc(picture.original.byteCount);
      const { bytesRead } = await saved.read(bytes);
      return bytesRead === bytes.length && matches(bytes, picture) ? bytes : null;
    } finally {
      await saved.close();
    }
  } catch (error) {
    if (["ENOENT", "ELOOP"].includes((error as NodeJS.ErrnoException).code ?? "")) return null;
    throw error;
  }
}

function matches(bytes: Uint8Array, { original }: ResearchQuotePictureV2): boolean {
  return bytes.byteLength === original.byteCount &&
    createHash("sha256").update(bytes).digest("hex") === original.sha256;
}
