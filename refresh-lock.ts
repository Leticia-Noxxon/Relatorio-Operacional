/** Lock em memória do processo Node (compartilhado entre rotas). */
let active: Promise<unknown> | null = null;

export function isRefreshRunning(): boolean {
  return active !== null;
}

export function setRefreshPromise(p: Promise<unknown> | null): void {
  active = p;
}

export function getRefreshPromise(): Promise<unknown> | null {
  return active;
}
