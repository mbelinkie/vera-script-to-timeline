import {
  createCipheriv,
  createDecipheriv,
  randomBytes,
} from "node:crypto";

export interface RestrictedRequestContext {
  readonly projectId: string;
  readonly captureId: string;
  readonly configurationVersion: number;
  readonly canonicalUrlDigest: string;
}

function aad(context: RestrictedRequestContext): Buffer {
  return Buffer.from(
    [
      context.projectId,
      context.captureId,
      String(context.configurationVersion),
      context.canonicalUrlDigest,
    ].join("\u0000"),
    "utf8",
  );
}

export class RestrictedRequestCipher {
  readonly keyVersion = 1;

  constructor(private readonly key: Buffer) {
    if (key.byteLength !== 32) {
      throw new TypeError("Restricted request encryption requires a 256-bit key.");
    }
  }

  encrypt(exactUrl: string, context: RestrictedRequestContext): Buffer {
    const nonce = randomBytes(12);
    const cipher = createCipheriv("aes-256-gcm", this.key, nonce);
    cipher.setAAD(aad(context));
    const ciphertext = Buffer.concat([
      cipher.update(exactUrl, "utf8"),
      cipher.final(),
    ]);
    return Buffer.concat([nonce, cipher.getAuthTag(), ciphertext]);
  }

  decrypt(envelope: Buffer, context: RestrictedRequestContext): string {
    if (envelope.byteLength < 29) {
      throw new Error("Restricted request envelope is invalid.");
    }
    const decipher = createDecipheriv(
      "aes-256-gcm",
      this.key,
      envelope.subarray(0, 12),
    );
    decipher.setAAD(aad(context));
    decipher.setAuthTag(envelope.subarray(12, 28));
    return Buffer.concat([
      decipher.update(envelope.subarray(28)),
      decipher.final(),
    ]).toString("utf8");
  }
}
