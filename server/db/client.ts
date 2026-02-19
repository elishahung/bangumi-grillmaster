import fs from 'node:fs';
import path from 'node:path';
import { env } from '@server/env';
import Database from 'better-sqlite3';
import { drizzle } from 'drizzle-orm/better-sqlite3';
import { migrate } from 'drizzle-orm/better-sqlite3/migrator';

const dbFile = path.resolve(process.cwd(), env.SQLITE_DB_PATH);
fs.mkdirSync(path.dirname(dbFile), { recursive: true });

const sqlite = new Database(dbFile);
export const db = drizzle(sqlite);

let initialized = false;

export const initDb = () => {
  if (initialized) {
    return;
  }

  migrate(db, {
    migrationsFolder: path.resolve(process.cwd(), 'drizzle'),
  });

  initialized = true;
};
