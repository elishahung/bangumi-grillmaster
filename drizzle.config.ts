import fs from 'node:fs';
import path from 'node:path';
import { defineConfig } from 'drizzle-kit';

const sqlitePath = process.env.SQLITE_DB_PATH ?? 'data/grillmaster.db';
const sqliteFilePath = path.resolve(process.cwd(), sqlitePath);
fs.mkdirSync(path.dirname(sqliteFilePath), { recursive: true });

export default defineConfig({
  dialect: 'sqlite',
  schema: './server/db/schema.ts',
  out: './drizzle',
  dbCredentials: {
    url: sqliteFilePath,
  },
});
