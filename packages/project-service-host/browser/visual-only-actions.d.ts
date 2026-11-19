/** Pure helpers accept untrusted rendered rows and refuse malformed input. */
export declare function visualOnlyIds(row: unknown): string[] | null;
export declare function planVisualOnlyReorder(
  row: unknown, draggedPayloadId: string, beforePayloadId?: string | null,
): { kind: "reorder_visual_only"; rowId: string; payloadIds: string[] } | null;
/** Return seconds rounded only through an exact positive millisecond count. */
export declare function parseHoldSeconds(raw: unknown): number | null;
