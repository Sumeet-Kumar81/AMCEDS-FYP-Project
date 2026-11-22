// Session tokens are kept in memory only (blueprint 07 §7.5): never in localStorage, so another
// script on the page or a shared computer cannot read them later. A page reload means signing in again.

export interface Tokens {
  accessToken: string;
  refreshToken: string;
}

type Listener = (tokens: Tokens | null) => void;

export class TokenStore {
  private tokens: Tokens | null = null;
  private listeners = new Set<Listener>();

  get(): Tokens | null {
    return this.tokens;
  }

  set(tokens: Tokens): void {
    this.tokens = tokens;
    this.emit();
  }

  clear(): void {
    if (this.tokens === null) return;
    this.tokens = null;
    this.emit();
  }

  /** Called with the new tokens (or null on sign-out). Returns the unsubscribe function. */
  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(): void {
    for (const listener of this.listeners) listener(this.tokens);
  }
}
