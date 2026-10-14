// Apaga o banco SQLite descartável dos testes E2E (e os arquivos -journal/-wal/-shm).
// Usado no lugar de `rm -f`, para funcionar também no Windows.
import { readdirSync, rmSync } from 'node:fs'
import path from 'node:path'

const db = process.argv[2]
if (!db) throw new Error('uso: node clean-db.mjs <caminho-do-banco>')
const dir = path.dirname(db)
const base = path.basename(db)
for (const name of readdirSync(dir)) {
  if (name.startsWith(base)) rmSync(path.join(dir, name), { force: true })
}
