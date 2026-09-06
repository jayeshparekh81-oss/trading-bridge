/**
 * Shop order (Simple picker and Pro grid alike): strategies with a public
 * proof record (a showcase entry joined by listing_id) come first; the rest
 * keep the API's order. Pure; shared by the marketplace page and its test.
 */
export function orderForShop<T extends { id: string }>(listings: T[], byListingId: Record<string, unknown>): T[] {
  const proven = listings.filter((l) => byListingId[l.id]);
  const rest = listings.filter((l) => !byListingId[l.id]);
  return [...proven, ...rest];
}
