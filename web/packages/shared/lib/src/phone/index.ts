/**
 * Uzbek phone numbers — 08-dizayn-tizimi.md §8 (`+998 XX XXX XX XX`), BO-01 `phone` field (07).
 * The login form shows a fixed "+998" prefix and the 9 national digits "90 123 45 67".
 * Digit filtering is character-based (no hand-written regex masks).
 */
export const UZ_COUNTRY_CODE = "998";
export const UZ_NATIONAL_LENGTH = 9;

/** Keeps only ASCII digits. */
export function onlyDigits(input: string): string {
  let out = "";
  for (const ch of input) {
    if (ch >= "0" && ch <= "9") out += ch;
  }
  return out;
}

/** National part (9 digits) from any user input; drops a leading 998 country code if pasted. */
export function nationalDigits(input: string): string {
  let digits = onlyDigits(input);
  if (digits.length > UZ_NATIONAL_LENGTH && digits.startsWith(UZ_COUNTRY_CODE)) {
    digits = digits.slice(UZ_COUNTRY_CODE.length);
  }
  return digits.slice(0, UZ_NATIONAL_LENGTH);
}

/** Live input mask for the national part: "901234567" → "90 123 45 67". */
export function maskNationalPhone(input: string): string {
  const d = nationalDigits(input);
  const groups = [d.slice(0, 2), d.slice(2, 5), d.slice(5, 7), d.slice(7, 9)];
  return groups.filter((g) => g.length > 0).join(" ");
}

export function isCompleteNationalPhone(input: string): boolean {
  return nationalDigits(input).length === UZ_NATIONAL_LENGTH;
}

/** E.164 for the API: "90 123 45 67" → "+998901234567". */
export function toE164(input: string): string {
  return `+${UZ_COUNTRY_CODE}${nationalDigits(input)}`;
}

/** Display: "+998901234567" → "+998 90 123 45 67". */
export function formatPhone(value: string): string {
  return `+${UZ_COUNTRY_CODE} ${maskNationalPhone(value)}`;
}
