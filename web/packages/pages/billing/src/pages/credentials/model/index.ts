/** One credential-set flow instance per page (features/credential-set/model). */
import { createCredentialSetModel } from "#/features/credential-set/model/index.ts";

export const recoverModel = createCredentialSetModel("recovery");
export const inviteModel = createCredentialSetModel("invite");
