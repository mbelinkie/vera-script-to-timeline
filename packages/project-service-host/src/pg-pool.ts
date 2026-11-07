import pg from "pg";

import type { SqlClient, SqlPool } from "@vera/project-authorization";

import type { QaConfig } from "./qa-config.js";

/** A bounded pool, shared by authorization and document services. */
export interface QaPgPool extends SqlPool {
  close(): Promise<void>;
}

export function createQaPgPool(
  config: QaConfig,
  onIdleError: () => void = () => undefined,
): QaPgPool {
  const backend = new pg.Pool({
    connectionString: config.databaseUrl,
    ssl: false, // QA DB is explicitly restricted to local loopback.
    max: 5,
    connectionTimeoutMillis: 5000,
    idleTimeoutMillis: 10_000,
  });
  // A disconnected idle client otherwise becomes an unhandled EventEmitter
  // error. The outer server can choose to stop/reconcile on this signal.
  backend.on("error", () => { onIdleError(); });
  return {
    connect: async (): Promise<SqlClient> => {
      const client = await backend.connect();
      return {
        query: async <R>(sql: string, parameters?: readonly unknown[]) => {
          const result = await client.query(sql, parameters ? [...parameters] : []);
          return { rows: result.rows as R[] };
        },
        release: () => { client.release(); },
      };
    },
    close: async () => { await backend.end(); },
  };
}
