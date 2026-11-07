import { beforeEach, describe, expect, it, vi } from "vitest";

const fake = vi.hoisted(() => {
  const release = vi.fn();
  const query = vi.fn().mockResolvedValue({ rows: [{ okay: true }] });
  const connect = vi.fn().mockResolvedValue({ query, release });
  const end = vi.fn().mockResolvedValue(undefined);
  const on = vi.fn();
  const Pool = vi.fn(function () { return { connect, end, on }; });
  return { Pool, release, query, connect, end, on };
});
vi.mock("pg", () => ({ default: { Pool: fake.Pool } }));

import { createQaPgPool } from "../src/pg-pool.js";
import type { QaConfig } from "../src/qa-config.js";

const config = {
  databaseUrl: "postgresql://qa:secret@127.0.0.1/vera_stt_qa_test",
} as QaConfig;

describe("PostgreSQL SQL pool adapter", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("uses a bounded pool, passes an immutable param copy and releases each client", async () => {
    const pool = createQaPgPool(config);
    expect(fake.Pool).toHaveBeenCalledWith({
      connectionString: config.databaseUrl,
      ssl: false,
      max: 5,
      connectionTimeoutMillis: 5000,
      idleTimeoutMillis: 10_000,
    });
    const client = await pool.connect();
    const params = ["x"];
    expect((await client.query("SELECT $1", params)).rows).toEqual([{ okay: true }]);
    expect(fake.query).toHaveBeenCalledWith("SELECT $1", ["x"]);
    expect(fake.query.mock.calls[0]?.[1]).not.toBe(params);
    client.release?.();
    expect(fake.release).toHaveBeenCalledTimes(1);
    await pool.close();
    expect(fake.end).toHaveBeenCalledTimes(1);
  });

  it("does not leak connection errors through logs and forwards idle error signal", () => {
    const onIdleError = vi.fn();
    createQaPgPool(config, onIdleError);
    const listener = fake.on.mock.calls.find(([event]) => event === "error")?.[1] as
      ((error: Error) => void) | undefined;
    expect(listener).toBeTypeOf("function");
    listener?.(new Error("secret connection failed"));
    expect(onIdleError).toHaveBeenCalledTimes(1);
  });
});
