import {
  createHash,
  createHmac,
  randomUUID,
  timingSafeEqual,
} from "node:crypto";

type JsonPrimitive = boolean | null | number | string;
export type JsonValue =
  | JsonPrimitive
  | readonly JsonValue[]
  | { readonly [key: string]: JsonValue };

function serialize(value: JsonValue): string {
  if (value === null || typeof value !== "object") {
    const encoded = JSON.stringify(value);
    if (
      encoded === undefined ||
      (typeof value === "number" && !Number.isFinite(value))
    ) {
      throw new TypeError("Only finite JSON values can be canonicalized.");
    }
    return encoded;
  }
  if (Array.isArray(value)) {
    return `[${value.map(serialize).join(",")}]`;
  }
  const object = value as Readonly<Record<string, JsonValue>>;
  return `{${Object.keys(object)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${serialize(object[key]!)}`)
    .join(",")}}`;
}

export function canonicalJson(value: JsonValue): string {
  return serialize(value);
}

export function sha256(value: Buffer | JsonValue | string): string {
  const bytes =
    Buffer.isBuffer(value)
      ? value
      : Buffer.from(
          typeof value === "string" ? value : canonicalJson(value),
          "utf8",
        );
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

export function stableUuid(parts: readonly (number | string)[]): string {
  const hex = createHash("sha256")
    .update(parts.map(String).join("\u0000"), "utf8")
    .digest("hex")
    .slice(0, 32)
    .split("");
  hex[12] = "5";
  hex[16] = ((Number.parseInt(hex[16]!, 16) & 0x3) | 0x8).toString(16);
  const value = hex.join("");
  return `${value.slice(0, 8)}-${value.slice(8, 12)}-${value.slice(12, 16)}-${value.slice(16, 20)}-${value.slice(20)}`;
}

export function keyedFingerprint(secret: Buffer, value: Buffer | string): string {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(value, "utf8");
  return `hmac-sha256-v1:${createHmac("sha256", secret)
    .update(bytes)
    .digest("hex")}`;
}

export class CapabilityError extends Error {
  override readonly name = "CapabilityError";

  constructor(readonly code: string) {
    super("The capability is invalid, expired, or outside its authorized scope.");
  }
}

type CapabilityScalar = boolean | number | string;
export type CapabilityScope = Readonly<Record<string, CapabilityScalar>>;

export interface CapabilityClaims extends CapabilityScope {
  readonly exp: number;
  readonly iat: number;
  readonly jti: string;
}

export interface IssuedCapability {
  readonly claims: CapabilityClaims;
  readonly token: string;
  readonly tokenDigest: string;
  readonly jtiDigest: string;
  readonly scopeDigest: string;
}

function parseClaims(encoded: string): CapabilityClaims {
  let value: unknown;
  try {
    value = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
  } catch {
    throw new CapabilityError("capability_malformed");
  }
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    typeof (value as Record<string, unknown>).exp !== "number" ||
    typeof (value as Record<string, unknown>).iat !== "number" ||
    typeof (value as Record<string, unknown>).jti !== "string"
  ) {
    throw new CapabilityError("capability_malformed");
  }
  for (const field of Object.values(value as Record<string, unknown>)) {
    if (!["boolean", "number", "string"].includes(typeof field)) {
      throw new CapabilityError("capability_malformed");
    }
  }
  return value as CapabilityClaims;
}

export class CapabilitySigner {
  constructor(private readonly secret: Buffer) {
    if (secret.byteLength < 32) {
      throw new TypeError("Capability signing keys must contain at least 32 bytes.");
    }
  }

  issue(scope: CapabilityScope, issuedAt: Date, expiresAt: Date): IssuedCapability {
    const iat = Math.floor(issuedAt.getTime() / 1000);
    const exp = Math.floor(expiresAt.getTime() / 1000);
    if (!Number.isFinite(iat) || !Number.isFinite(exp) || exp <= iat) {
      throw new TypeError("A capability expiry must follow its issue time.");
    }
    const claims: CapabilityClaims = {
      ...scope,
      exp,
      iat,
      jti: randomUUID(),
    };
    const encoded = Buffer.from(
      canonicalJson(claims as unknown as JsonValue),
      "utf8",
    ).toString("base64url");
    const signature = createHmac("sha256", this.secret)
      .update(encoded)
      .digest("base64url");
    const token = `${encoded}.${signature}`;
    return {
      claims,
      token,
      tokenDigest: sha256(token),
      jtiDigest: sha256(claims.jti),
      scopeDigest: sha256(scope),
    };
  }

  verify(
    token: string,
    now: Date,
    expectedScope: CapabilityScope = {},
    options: { readonly allowExpired?: boolean } = {},
  ): CapabilityClaims {
    const parts = token.split(".");
    if (parts.length !== 2 || !parts[0] || !parts[1]) {
      throw new CapabilityError("capability_malformed");
    }
    const expected = createHmac("sha256", this.secret)
      .update(parts[0])
      .digest();
    let actual: Buffer;
    try {
      actual = Buffer.from(parts[1], "base64url");
    } catch {
      throw new CapabilityError("capability_malformed");
    }
    if (actual.byteLength !== expected.byteLength || !timingSafeEqual(actual, expected)) {
      throw new CapabilityError("capability_invalid");
    }
    const claims = parseClaims(parts[0]);
    const current = Math.floor(now.getTime() / 1000);
    if (!Number.isFinite(current) || current < claims.iat) {
      throw new CapabilityError("capability_not_yet_valid");
    }
    if (current >= claims.exp && !options.allowExpired) {
      throw new CapabilityError("capability_expired");
    }
    for (const [key, value] of Object.entries(expectedScope)) {
      if (claims[key] !== value) {
        throw new CapabilityError("capability_scope_mismatch");
      }
    }
    return claims;
  }
}
