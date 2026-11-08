import { randomUUID } from "node:crypto";

import { ProjectAuthorizationService } from "@vera/project-authorization";
import { describe, expect, it, vi } from "vitest";

import { applyQaMigrations } from "../src/migrate.js";
import { createQaPgPool } from "../src/pg-pool.js";
import { parseQaConfig } from "../src/qa-config.js";

// Only a dedicated disposable vera_stt_qa_* DB owned by an unprivileged role.
const testUrl = process.env.VERA_STT_QA_TEST_DATABASE_URL;
const postgres = testUrl ? describe : describe.skip;
vi.setConfig({ testTimeout: 30_000 });

postgres("real PostgreSQL QA migrations", () => {
  it("repeats checksum-verified auth/docs migration on populated PostgreSQL", async () => {
    const sha = "a".repeat(40);
    const config = parseQaConfig({
      VERA_STT_MODE: "development-qa",
      VERA_STT_QA_HOST: "127.0.0.1",
      VERA_STT_QA_PORT: "38429",
      VERA_STT_QA_DATABASE_URL: testUrl,
      VERA_STT_QA_IDENTITY_FILE: "/tmp/vera-qa-synthetic-identity.json",
      VERA_STT_SOURCE_SHA: sha,
    }, sha);
    const pool = createQaPgPool(config);
    try {
      const first = await applyQaMigrations(pool, config);
      const auth = new ProjectAuthorizationService(pool);
      const actor = await auth.resolveActor({
        issuer: "https://qa.synthetic.invalid", subject: randomUUID(),
      });
      expect(await applyQaMigrations(pool, config)).toEqual(first);
      const db = await pool.connect();
      try {
        const actors = await db.query<{ n: number }>(
          "SELECT count(*)::integer AS n FROM vera_identity_actors WHERE id=$1",
          [actor.principalId],
        );
        expect(actors.rows[0]?.n).toBe(1);
        const migrations = await db.query<{ n: number }>(
          "SELECT count(*)::integer AS n FROM vera_schema_migrations",
        );
          expect(migrations.rows[0]?.n).toBe(4);
      } finally {
        db.release?.();
      }
    } finally {
      await pool.close();
    }
  });
});
