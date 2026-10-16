import { ESLint, RuleTester } from "eslint";
import tseslint from "typescript-eslint";
import { afterAll, describe, expect, it } from "vitest";

import { createConfig } from "../index.js";
import { lucideViaIcon } from "../rules/lucide-via-icon.js";
import { noMoneyArithmetic } from "../rules/no-money-arithmetic.js";

RuleTester.afterAll = afterAll;
RuleTester.describe = describe;
RuleTester.it = it;

const fixtureDir = new URL("./fixture/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

const typed = new RuleTester({
  languageOptions: {
    parser: tseslint.parser,
    parserOptions: { project: "./tsconfig.json", tsconfigRootDir: fixtureDir },
  },
});

const MONEY = `type Money = string & { readonly __brand: "Money" };
declare const a: Money;
declare const b: Money;
declare const s: string;
`;

typed.run("erp/no-money-arithmetic (qaror #57)", noMoneyArithmetic, {
  valid: [
    { code: `${MONEY}const label = s + "!";`, filename: `${fixtureDir}file.ts` },
    { code: `${MONEY}const ok = a === b;`, filename: `${fixtureDir}file.ts` },
    { code: "const n = 1 + 2;", filename: `${fixtureDir}file.ts` },
  ],
  invalid: [
    { code: `${MONEY}const c = a + b;`, filename: `${fixtureDir}file.ts`, errors: [{ messageId: "moneyArithmetic" }] },
    { code: `${MONEY}const c = a * 2;`, filename: `${fixtureDir}file.ts`, errors: [{ messageId: "moneyArithmetic" }] },
    { code: `${MONEY}let c = s; c += a;`, filename: `${fixtureDir}file.ts`, errors: [{ messageId: "moneyArithmetic" }] },
    { code: `${MONEY}const c = -a;`, filename: `${fixtureDir}file.ts`, errors: [{ messageId: "moneyArithmetic" }] },
    {
      code: `${MONEY}const c = (a as Money | null) ?? b; const d = c + "";`,
      filename: `${fixtureDir}file.ts`,
      errors: [{ messageId: "moneyArithmetic" }],
    },
  ],
});

const jsx = new RuleTester({
  languageOptions: { parser: tseslint.parser, parserOptions: { ecmaFeatures: { jsx: true } } },
});

jsx.run("erp/lucide-via-icon (24 §4.2)", lucideViaIcon, {
  valid: [
    `import { Bell } from "lucide-react"; const x = <Icon as={Bell} />;`,
    `import { Bell } from "./local"; const x = <Bell />;`,
  ],
  invalid: [{ code: `import { Bell } from "lucide-react"; const x = <Bell />;`, errors: [{ messageId: "direct" }] }],
});

describe("shared config: no-implicit-coercion (qaror #57, 32 §3.3)", () => {
  const eslint = new ESLint({
    cwd: fixtureDir,
    overrideConfigFile: true,
    overrideConfig: createConfig({ tsconfigRootDir: fixtureDir, kind: "shared" }),
  });
  const ruleIds = async (code) => {
    const [result] = await eslint.lintText(code, { filePath: `${fixtureDir}file.ts` });
    return result.messages.map((m) => m.ruleId);
  };

  it("reports unary + on a string amount", async () => {
    const code = ['export const amount: string = "12000.00";', "export const n = +amount;", ""].join("\n");
    expect(await ruleIds(code)).toContain("no-implicit-coercion");
  });

  it("allows !!flag and String() conversion", async () => {
    const code = ["const flag: unknown = 1;", "export const b = !!flag;", "export const s = String(flag);", ""].join("\n");
    const ids = await ruleIds(code);
    expect(ids).not.toContain("no-implicit-coercion");
  });
});
