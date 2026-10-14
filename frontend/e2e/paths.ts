import path from 'node:path'

// Caminhos usados pela configuração do Playwright e pelos auxiliares dos testes.
// Funcionam em Linux, macOS e Windows (o venv usa Scripts\python.exe no Windows).
export const backendDir = path.resolve(import.meta.dirname, '../../backend')
export const python =
  process.env.E2E_PYTHON ??
  (process.platform === 'win32'
    ? path.join(backendDir, '.venv', 'Scripts', 'python.exe')
    : path.join(backendDir, '.venv', 'bin', 'python'))
export const E2E_DB = path.join(backendDir, 'e2e.db')
export const E2E_DATABASE_URL = `sqlite:///${E2E_DB}`
