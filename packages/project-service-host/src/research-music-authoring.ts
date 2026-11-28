import { isDeepStrictEqual } from "node:util";
import { isResearchId, ResearchReadError } from "@vera/contracts/research-clip-client";
import type { RowAudioSourceV2 } from "@vera/contracts/v2";
import { ProjectAuthError } from "@vera/project-authorization";
import type { AuthoringResearchAccess } from "./authoring.js";
import { runResearchMediaWorker, type ResearchMediaConfig } from "./research-media-authoring.js";

export interface PreparedResearchMusic {
  source: RowAudioSourceV2;
  durationSamples: number;
}

/** Resolve a picker candidate inside the authorized cue command. Only this result is trusted. */
export async function resolveResearchMusicSource(
  research: AuthoringResearchAccess,
  config: ResearchMediaConfig | undefined,
  timelineProjectId: string,
  researchProjectId: string,
  expected: unknown,
): Promise<PreparedResearchMusic> {
  if (!isResearchId(timelineProjectId) || !isResearchId(researchProjectId) ||
      typeof expected !== "object" || expected === null || !("itemId" in expected) ||
      typeof expected.itemId !== "string" || !isResearchId(expected.itemId)) {
    throw new ResearchReadError(400, "Choose a saved Research Music selection.");
  }
  const projectId = timelineProjectId.toLowerCase();
  const catalogProjectId = researchProjectId.toLowerCase();
  const itemId = expected.itemId;
  const { catalog } = research;
  const { musicSelection, musicPlayback } = catalog;
  if (config?.projectId !== projectId || !musicSelection || !musicPlayback) {
    throw new ResearchReadError(503, "Research Music preparation is unavailable for this project.");
  }
  const readCurrent = async () => {
    try {
      await research.authorizeTimelineProject(projectId, "edit_document");
      const visible = await catalog.projects();
      if (!visible.some(({ id }) => id.toLowerCase() === catalogProjectId)) {
        throw new ResearchReadError(403, "You do not have access to this Research project.");
      }
      const current = await musicSelection(catalogProjectId, itemId);
      if (!isDeepStrictEqual(expected, current.selection)) {
        throw new ResearchReadError(409, "The saved Music selection changed. Reload Music choices and select it again.");
      }
      return current;
    } catch (error) {
      if (error instanceof ResearchReadError || error instanceof ProjectAuthError) throw error;
      throw new ResearchReadError(503, "The Music selection could not be checked. Reload Music choices and retry.");
    }
  };
  const { selection, mimeType } = await readCurrent();
  const bytes = await musicPlayback(catalogProjectId, selection.sourceId, mimeType, selection.playbackHash).catch((error: unknown) => {
    if (error instanceof ResearchReadError) throw error;
    throw new ResearchReadError(422, "Research could not supply verified kept audio for this selection.");
  });
  let prepared: PreparedResearchMusic;
  try {
    prepared = JSON.parse((await runResearchMediaWorker(config, {
      action: "prepare_music", projectId, selection, mimeType,
    }, bytes)).toString()) as PreparedResearchMusic;
  } catch {
    throw new ResearchReadError(422, "The kept audio could not supply a verified WAV for the exact saved range.");
  }
  await readCurrent();
  return prepared;
}
