# #6 Finish Dev objective #3: regenerate BO-10 OpenAPI clients

Background: the previous Dev team (closed; branch team/7/dev-61395f kept with 39 unlanded commits) implemented the audited stage 5 gaps, the BO-10 state-report API and two login fixes. Read the Brain note 'Dev team handoff before recreation (2026-10-23)' first.

Do: (1) bring branch team/7/dev-61395f into your lane branch (merge, no history loss, discard nothing; never touch the user's uncommitted work on impl/bosqich-5 in E:/Project/erp). (2) From web/: pnpm install --frozen-lockfile, then pnpm api:export and pnpm api:gen (uv and Python 3.13 are on PATH). (3) Review the diff and commit only the intended openapi.json and generated tax/models artifacts for BO-10 upload/history. (4) Run web typecheck and the BO-10 backend tests.

Proof: committed generated clients, typecheck and BO-10 tests green. Escalate to the mega-lead instead of guessing.
