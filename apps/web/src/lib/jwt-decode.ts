/** Decodes a JWT's payload without verifying its signature — this is NOT a security check
 * (the backend always verifies independently on every request), it's purely for reading a
 * claim the client already holds in plaintext (the token itself isn't encrypted, just
 * signed) to answer questions like "which participant record in this room is mine" without
 * a server round-trip. Returns null on any malformed input rather than throwing, since this
 * is read for UI convenience, not something that should ever crash a render. */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = payload + "=".repeat((4 - (payload.length % 4)) % 4);
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}
