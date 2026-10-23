/**
 * E-IMZO signer for the back office (21 §5, 19 §8a/§19/§20, 18 §14a). Pure TS, no React.
 *
 * Flow (server side in `integrations.einvoice`): `POST …/sign-challenge` → `{document_hash, challenge_id}` →
 * the browser signs **the `document_hash` string itself** as an attached PKCS#7 with the user's E-IMZO key →
 * `POST …/submit-signed {challenge_id, signature_pkcs7}` (or e-TTN `accept`/`reject`).
 *
 * Adapters behind {@link EimzoSigner}:
 * - **fake** (dev / test / staging, never production): one test key; the PKCS#7 is
 *   `base64("FAKE-PKCS7\n<serial>\n<tin>\n" + content)` — exactly what the backend `FakeSignatureVerifier`
 *   (`ERP_EIMZO_VERIFIER=fake`) accepts.
 * - **unavailable** (production until 26 #118): the real E-IMZO client needs the production API-KEY for the
 *   single signing domain `sign.<domen>` and E-IMZO-SERVER on the backend; until then every call fails with
 *   `EIMZO_UNAVAILABLE` and the UI explains why — nothing is signed with an unverified key.
 */
import { getRuntimeConfig } from "#/runtime-config/index.ts";

export interface EimzoKey {
  /** Adapter-local key id (certificate serial for the fake). */
  id: string;
  /** Certificate owner (full name / organisation). */
  owner: string;
  /** STIR (organisation) or JShShIR (person) from the certificate. */
  tin: string;
  serial: string;
  /** Role / position from the certificate, when present. */
  role: string | null;
  /** `YYYY-MM-DD` — the certificate is not valid after this day. */
  validTo: string;
}

export type EimzoErrorCode = "EIMZO_UNAVAILABLE" | "EIMZO_NO_KEYS" | "EIMZO_KEY_EXPIRED" | "EIMZO_CANCELLED";

/** i18n: `common:eimzo.errors.<code>`. */
export class EimzoError extends Error {
  readonly code: EimzoErrorCode;

  constructor(code: EimzoErrorCode) {
    super(code);
    this.name = "EimzoError";
    this.code = code;
  }
}

export interface EimzoSigner {
  readonly kind: "fake" | "unavailable";
  /** Keys available in the local E-IMZO (PFX / ID-card). */
  listKeys(): Promise<EimzoKey[]>;
  /** Attached PKCS#7 (base64) over `content` with the key `keyId`. */
  sign(keyId: string, content: string): Promise<string>;
}

const FAKE_MAGIC = "FAKE-PKCS7\n";

function utf8Base64(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

/** The PKCS#7 a fake key produces (mirrors backend `fake_pkcs7`). */
export function fakePkcs7(content: string, serial = "FAKE0001", tin = "123456789"): string {
  return utf8Base64(`${FAKE_MAGIC}${serial}\n${tin}\n${content}`);
}

export const FAKE_KEY: Readonly<EimzoKey> = Object.freeze({
  id: "FAKE0001",
  owner: "TEST DIREKTOR (TestCA)",
  tin: "123456789",
  serial: "FAKE0001",
  role: "Direktor",
  validTo: "2099-12-31",
});

export function createFakeEimzoSigner(keys: readonly EimzoKey[] = [FAKE_KEY]): EimzoSigner {
  return {
    kind: "fake",
    listKeys: () => Promise.resolve(keys.map((k) => ({ ...k }))),
    sign: (keyId, content) => {
      const key = keys.find((k) => k.id === keyId);
      if (!key) return Promise.reject(new EimzoError("EIMZO_NO_KEYS"));
      return Promise.resolve(fakePkcs7(content, key.serial, key.tin));
    },
  };
}

/** Production adapter until the E-IMZO API-KEY / E-IMZO-SERVER contract exists (26 #118). */
export function createUnavailableEimzoSigner(): EimzoSigner {
  return {
    kind: "unavailable",
    listKeys: () => Promise.reject(new EimzoError("EIMZO_UNAVAILABLE")),
    sign: () => Promise.reject(new EimzoError("EIMZO_UNAVAILABLE")),
  };
}

let override: EimzoSigner | null = null;

/** Tests / stories replace the signer for the page load. */
export function setEimzoSigner(signer: EimzoSigner | null): void {
  override = signer;
}

/** The signer of this environment: fake outside production, unavailable in production (26 #118). */
export function getEimzoSigner(): EimzoSigner {
  if (override) return override;
  return getRuntimeConfig().environment === "production"
    ? createUnavailableEimzoSigner()
    : createFakeEimzoSigner();
}

/** `validTo` is before `today` (both `YYYY-MM-DD`). */
export function isKeyExpired(key: Pick<EimzoKey, "validTo">, today: string): boolean {
  return key.validTo < today;
}

export interface SignFlow<C> {
  /** `POST …/sign-challenge` (any extra query, e.g. `?action=accept`, is the caller's). */
  challenge: () => Promise<{ document_hash: string; challenge_id: string }>;
  /** `POST …/submit-signed` (or the e-TTN `accept`/`reject` body). */
  submit: (body: { challenge_id: string; signature_pkcs7: string }) => Promise<C>;
}

/** challenge → sign the hash with `keyId` → submit. Errors: {@link EimzoError} or the API error as thrown. */
export async function signDocument<C>(
  signer: EimzoSigner,
  key: Pick<EimzoKey, "id" | "validTo">,
  flow: SignFlow<C>,
  today: string,
): Promise<C> {
  if (isKeyExpired(key, today)) throw new EimzoError("EIMZO_KEY_EXPIRED");
  const { document_hash, challenge_id } = await flow.challenge();
  const signature_pkcs7 = await signer.sign(key.id, document_hash);
  return flow.submit({ challenge_id, signature_pkcs7 });
}
