import { afterEach, describe, expect, it } from "vitest";

import {
  EimzoError,
  FAKE_KEY,
  createFakeEimzoSigner,
  createUnavailableEimzoSigner,
  fakePkcs7,
  getEimzoSigner,
  setEimzoSigner,
  signDocument,
} from "./index.ts";

afterEach(() => setEimzoSigner(null));

describe("E-IMZO signer", () => {
  it("fake PKCS#7 has the backend FakeSignatureVerifier format", () => {
    const blob = fakePkcs7("ab12", "S1", "305112847");
    expect(atob(blob)).toBe("FAKE-PKCS7\nS1\n305112847\nab12");
  });

  it("signDocument: challenge → sign the hash → submit", async () => {
    const calls: string[] = [];
    const result = await signDocument(
      createFakeEimzoSigner(),
      FAKE_KEY,
      {
        challenge: () => {
          calls.push("challenge");
          return Promise.resolve({ document_hash: "deadbeef", challenge_id: "c-1" });
        },
        submit: (body) => {
          calls.push("submit");
          return Promise.resolve(body);
        },
      },
      "2026-10-18",
    );
    expect(calls).toEqual(["challenge", "submit"]);
    expect(result).toEqual({ challenge_id: "c-1", signature_pkcs7: fakePkcs7("deadbeef") });
  });

  it("expired key is refused before the challenge", async () => {
    const expired = { ...FAKE_KEY, validTo: "2020-01-01" };
    await expect(
      signDocument(
        createFakeEimzoSigner([expired]),
        expired,
        {
          challenge: () => Promise.reject(new Error("not called")),
          submit: () => Promise.reject(new Error("not called")),
        },
        "2026-10-18",
      ),
    ).rejects.toMatchObject({ code: "EIMZO_KEY_EXPIRED" });
  });

  it("unavailable adapter (production, 26 #118) never signs", async () => {
    const signer = createUnavailableEimzoSigner();
    await expect(signer.listKeys()).rejects.toBeInstanceOf(EimzoError);
    await expect(signer.sign("x", "y")).rejects.toMatchObject({ code: "EIMZO_UNAVAILABLE" });
  });

  it("getEimzoSigner: fake outside production, override wins", () => {
    expect(getEimzoSigner().kind).toBe("fake");
    const custom = createUnavailableEimzoSigner();
    setEimzoSigner(custom);
    expect(getEimzoSigner()).toBe(custom);
  });
});
