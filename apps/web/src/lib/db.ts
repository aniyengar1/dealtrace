import "server-only";

import path from "path";
import { Pool, types } from "pg";
import { config as loadEnv } from "dotenv";

// node-postgres returns NUMERIC as a string by default (to avoid silent
// float precision loss on arbitrary-precision decimals) and DATE as a
// JS Date constructed at local midnight, which toISOString() then shifts
// across a UTC day boundary -- a classic off-by-one bug for west-of-UTC
// timezones. Neither matters for this app (prices fit safely in a float,
// dates are only ever displayed/compared as plain ISO strings), so both
// come back as plain values instead: NUMERIC (oid 1700) as a number,
// DATE (oid 1082) as the raw "YYYY-MM-DD" string untouched.
types.setTypeParser(1700, (value) => (value === null ? null : parseFloat(value)));
types.setTypeParser(1082, (value) => value);

// DATABASE_URL lives in the repo root .env (the same file the Python
// pipeline reads), not a copy in apps/web -- one source of truth for
// local Postgres today and Supabase later, switched by editing one line
// in one place. The `server-only` import above makes it a build error to
// import this module from a Client Component, so the connection string
// can never reach the browser bundle.
loadEnv({ path: path.resolve(process.cwd(), "../../.env") });

declare global {
  var __dealtracePool: Pool | undefined;
}

function getPool(): Pool {
  if (!global.__dealtracePool) {
    const databaseUrl = process.env.DATABASE_URL;
    if (!databaseUrl) {
      throw new Error("DATABASE_URL is not set -- check the repo root .env");
    }
    // Cached on `global` so Next.js's dev-mode module reloading doesn't
    // open a fresh pool on every file edit.
    global.__dealtracePool = new Pool({ connectionString: databaseUrl });
  }
  return global.__dealtracePool;
}

export async function query<T>(text: string, params: unknown[] = []): Promise<T[]> {
  const pool = getPool();
  const result = await pool.query(text, params);
  return result.rows as T[];
}

export async function queryOne<T>(text: string, params: unknown[] = []): Promise<T | null> {
  const rows = await query<T>(text, params);
  return rows[0] ?? null;
}
