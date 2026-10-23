/** `units.is_fractional = true` codes from the catalog pull (context.ts keeps it current). */
let fractionalUnits: ReadonlySet<string> = new Set();

export function setFractionalUnits(codes: Iterable<string>): void {
  fractionalUnits = new Set(codes);
}

export function unitIsFractional(code: string): boolean {
  return fractionalUnits.has(code);
}
