import * as decoding from "lib0/decoding";
import * as encoding from "lib0/encoding";

import type { LiveStatus } from "./service.js";

/**
 * Wire format: one binary message, a type number then its payload.
 * It carries the same Yjs sync and awareness payloads as y-websocket, plus an
 * explicit acknowledgement so a client can tell "sent" from "safely stored".
 */
export const MESSAGE = {
  /** Either side: "here is what I have" (a Yjs state vector). */
  stateVector: 0,
  /** Server to client: Yjs update to apply. */
  update: 1,
  /** Client to server: numbered Yjs update to store. */
  clientUpdate: 2,
  /** Either side: presence (y-protocols awareness update). Never stored. */
  awareness: 3,
  /** Server to client: sync status, and the highest client update number stored. */
  status: 4,
  /** Server to client: a client update was not stored. */
  refused: 5,
  /** Server to client: who is connected. */
  roster: 6,
} as const;

export interface StatusMessage {
  status: LiveStatus;
  actorId: string;
  canEdit: boolean;
  /** Highest numbered update from this connection that is durably stored. */
  ackedSeq: number;
}

export interface RefusedMessage { code: string; seq: number }

export interface RosterEntry { actorId: string; canEdit: boolean; awarenessClientIds: number[] }

export type Message =
  | { type: "stateVector"; stateVector: Uint8Array }
  | { type: "update"; update: Uint8Array }
  | { type: "clientUpdate"; seq: number; update: Uint8Array }
  | { type: "awareness"; update: Uint8Array }
  | { type: "status"; body: StatusMessage }
  | { type: "refused"; body: RefusedMessage }
  | { type: "roster"; body: RosterEntry[] };

export function encodeMessage(message: Message): Uint8Array {
  const encoder = encoding.createEncoder();
  encoding.writeVarUint(encoder, MESSAGE[message.type]);
  switch (message.type) {
    case "stateVector": encoding.writeVarUint8Array(encoder, message.stateVector); break;
    case "update": encoding.writeVarUint8Array(encoder, message.update); break;
    case "clientUpdate":
      encoding.writeVarUint(encoder, message.seq);
      encoding.writeVarUint8Array(encoder, message.update);
      break;
    case "awareness": encoding.writeVarUint8Array(encoder, message.update); break;
    default: encoding.writeVarString(encoder, JSON.stringify(message.body));
  }
  return encoding.toUint8Array(encoder);
}

/** Returns null for anything malformed; callers drop it. */
export function decodeMessage(bytes: Uint8Array): Message | null {
  try {
    const decoder = decoding.createDecoder(bytes);
    const type = decoding.readVarUint(decoder);
    switch (type) {
      case MESSAGE.stateVector: return { type: "stateVector", stateVector: decoding.readVarUint8Array(decoder) };
      case MESSAGE.update: return { type: "update", update: decoding.readVarUint8Array(decoder) };
      case MESSAGE.clientUpdate: {
        const seq = decoding.readVarUint(decoder);
        return { type: "clientUpdate", seq, update: decoding.readVarUint8Array(decoder) };
      }
      case MESSAGE.awareness: return { type: "awareness", update: decoding.readVarUint8Array(decoder) };
      case MESSAGE.status: return { type: "status", body: JSON.parse(decoding.readVarString(decoder)) as StatusMessage };
      case MESSAGE.refused: return { type: "refused", body: JSON.parse(decoding.readVarString(decoder)) as RefusedMessage };
      case MESSAGE.roster: return { type: "roster", body: JSON.parse(decoding.readVarString(decoder)) as RosterEntry[] };
      default: return null;
    }
  } catch {
    return null;
  }
}

/** The Yjs client IDs named in a y-protocols awareness update. */
export function awarenessClientIds(update: Uint8Array): number[] | null {
  try {
    const decoder = decoding.createDecoder(update);
    const count = decoding.readVarUint(decoder);
    const ids: number[] = [];
    for (let index = 0; index < count; index += 1) {
      ids.push(decoding.readVarUint(decoder));
      decoding.readVarUint(decoder);
      decoding.readVarString(decoder);
    }
    return ids;
  } catch {
    return null;
  }
}
