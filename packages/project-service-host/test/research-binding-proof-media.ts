import { execFile as execFileCallback } from "node:child_process";
import { createHash } from "node:crypto";
import { appendFile, mkdir, readFile, realpath, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import type {
  OccurrenceMediaResolutionV2,
  ResearchClipSnapshotV2,
  ResearchFrameBindingV2,
  VisualOnlyBlockV2,
} from "@vera/contracts/v2";
import type { ResearchCutTranscriptClock } from "@vera/contracts/research-clip-client";

const execFile = promisify(execFileCallback);
const repository = fileURLToPath(new URL("../../../", import.meta.url));
const width = 64;
const height = 64;
const frameColors = [
  [220, 25, 25], [25, 220, 25], [25, 25, 220], [220, 220, 25],
  [220, 25, 220], [25, 220, 220], [220, 220, 220], [25, 25, 25],
] as const;

const encode = [
  "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
  "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
  "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
  "-color_range", "tv", "-g", "1", "-c:a", "aac", "-movflags", "+faststart",
];

const verify = `
import hashlib
import json
import sys
from pathlib import Path

from vera_timeline_agent.media_preparation import MediaTools
from vera_timeline_agent.research_cut_binding import bind_research_cut, cut_identity

row = json.loads(sys.argv[1])
snapshot = row["researchClip"]
folder = Path(sys.argv[2])
clip_id = snapshot["clipId"]
if sys.argv[3] == "create":
    artifacts = []
    for media in sorted(folder.iterdir()):
        data = media.read_bytes()
        artifacts.append({"name": media.name, "sha256": hashlib.sha256(data).hexdigest(),
                          "byteSize": len(data)})
    record = {**cut_identity(snapshot), "artifacts": artifacts}
    clock = json.loads(sys.argv[4])
    if clock:
        digest = next(item["sha256"] for item in artifacts if item["name"] == f"{clip_id}.mp4")
        record.update(transcriptVersionId=clock["transcriptVersionId"],
                      transcriptClock={**clock, "mediaSha256": digest})
    (folder / f"{clip_id}.json").write_text(json.dumps(record))
_, media, descriptor = bind_research_cut(row, folder, MediaTools())
print(json.dumps({"binding": row["frameBinding"], "descriptor": descriptor,
                  "digest": media.content_hash}))
`;

/** Builds a real disposable cut with a source frame number encoded in each picture. */
export async function makeResearchBindingProofMedia(
  root: string, snapshot: ResearchClipSnapshotV2, rowId: string, payloadId: string,
  clock?: Omit<ResearchCutTranscriptClock, "mediaSha256">,
) {
  const proofRoot = await realpath(root);
  const folder = join(proofRoot, "verified-cut");
  await mkdir(folder);
  const raw = join(proofRoot, "frames.rgb");
  const frameBytes = frameColors.map((color, frameIndex) => {
    const bytes = Buffer.alloc(width * height * 3);
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const bit = Math.floor(x / 8);
        const marker = y < 8 && bit < 3;
        const gray = (frameIndex & (1 << bit)) === 0 ? 0 : 255;
        bytes.set(marker ? [gray, gray, gray] : color, (y * width + x) * 3);
      }
    }
    return bytes;
  });
  await writeFile(raw, Buffer.concat(frameBytes));
  const path = join(folder, `${snapshot.clipId}.mp4`);
  await execFile("ffmpeg", [
    "-v", "error", "-nostdin", "-f", "rawvideo", "-pixel_format", "rgb24",
    "-video_size", `${width}x${height}`, "-framerate", "24000/1001", "-i", raw,
    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
    "-vf", "scale=out_color_matrix=bt709,setsar=1", "-shortest", ...encode, path,
  ]);
  if (clock) {
    const fields = [...Object.keys(clock), "denominator", "numerator"].sort();
    const payload = createHash("sha256").update(JSON.stringify(clock, fields)).digest();
    const header = Buffer.alloc(24);
    header.writeUInt32BE(header.length + payload.length);
    header.write("uuid", 4);
    header.write("8a4266a98b524776bd451c894db33d53", 8, "hex");
    await appendFile(path, Buffer.concat([header, payload]));
  }
  await writeFile(join(folder, `${snapshot.clipId}.en.srt`),
    "1\n00:00:00,042 --> 00:00:00,292\nGenerated media proof\n");
  const python = process.env.VERA_PROOF_PYTHON;
  async function bind(row: unknown, action: "create" | "rebind") {
    const { stdout } = await execFile(python ?? "uv", [
      ...(python ? [] : ["run", "--no-sync", "--frozen", "python"]),
      "-c", verify, JSON.stringify(row), folder, action, JSON.stringify(clock ?? null),
    ], { cwd: repository, env: { ...process.env, PYTHONPATH: join(repository, "python") } });
    return JSON.parse(stdout) as {
      binding: ResearchFrameBindingV2;
      descriptor: OccurrenceMediaResolutionV2;
      digest: string;
    };
  }
  const proof = await bind({ id: rowId, researchClip: snapshot, payload: { payloadId },
    visualOnlyTiming: { kind: "visual_only" } }, "create");
  const manifestPath = join(folder, `${snapshot.clipId}.json`);
  const initialManifest = await readFile(manifestPath);
  async function rebind(row: VisualOnlyBlockV2) {
    const rebound = await bind(row, "rebind");
    if (rebound.digest !== proof.digest ||
        rebound.descriptor.sourceSnapshot.probeHash !== proof.descriptor.sourceSnapshot.probeHash ||
        !(await readFile(manifestPath)).equals(initialManifest)) {
      throw new Error("Rebinding changed the verified Research media identity");
    }
    return rebound.descriptor;
  }
  const sourceFrameMap = proof.descriptor.sourceFrameMap;
  if (proof.binding.loggedEndFrame !== frameColors.length ||
      sourceFrameMap.decodedPackageFrameRate.numerator !== 24000 ||
      sourceFrameMap.decodedPackageFrameRate.denominator !== 1001) {
    throw new Error("Generated cut's verified frame bounds or cadence changed");
  }
  return { path, digest: proof.digest, rebind };
}
