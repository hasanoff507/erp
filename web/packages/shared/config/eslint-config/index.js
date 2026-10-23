/**
 * Shared ESLint flat config — 24-frontend-arxitekturasi.md §1 (FSD import rules), §4 (code quality,
 * money rule), §4.2 (lucide), 32-kod-qoidalari.md §3.3 / §5.2, qaror #57.
 *
 * Usage (per workspace package):
 *   import { createConfig } from "@shared/eslint-config";
 *   export default createConfig({ tsconfigRootDir: import.meta.dirname, kind: "pages" });
 */
import js from "@eslint/js";
import boundaries from "eslint-plugin-boundaries";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

import { lucideViaIcon } from "./rules/lucide-via-icon.js";
import { noMoneyArithmetic } from "./rules/no-money-arithmetic.js";

export const erpPlugin = {
  meta: { name: "erp" },
  rules: {
    "no-money-arithmetic": noMoneyArithmetic,
    "lucide-via-icon": lucideViaIcon,
  },
};

/** qaror #57: Number( / parseFloat( / parseInt( are banned (money must stay a decimal string). */
const moneyRestrictedSyntax = [
  {
    selector: "CallExpression[callee.name='Number']",
    message: "Number(...) taqiqlangan — pul/miqdor uchun @shared/lib/money (decimal.js) ishlating (qaror #57).",
  },
  {
    selector: "NewExpression[callee.name='Number']",
    message: "new Number(...) taqiqlangan (qaror #57).",
  },
  {
    selector: "CallExpression[callee.name=/^(parseFloat|parseInt)$/]",
    message: "parseFloat/parseInt taqiqlangan — @shared/lib/money ishlating (qaror #57).",
  },
  {
    selector: "CallExpression[callee.object.name='Number'][callee.property.name=/^(parseFloat|parseInt)$/]",
    message: "Number.parseFloat/parseInt taqiqlangan — @shared/lib/money ishlating (qaror #57).",
  },
  // 24 §4.2 — namespace import pulls the whole icon set into the bundle.
  {
    selector: "ImportDeclaration[source.value='lucide-react'] > ImportNamespaceSpecifier",
    message: "lucide-react faqat nomli import bilan (import { ScanLine } from 'lucide-react') — 24 §4.2.",
  },
  // 24 Asosiy xulosa #7 / 32 §5.1: raw JSON is never shown to the user.
  {
    selector: "JSXExpressionContainer CallExpression[callee.object.name='JSON'][callee.property.name='stringify']",
    message: "Foydalanuvchiga JSON.stringify ko'rsatilmaydi — message_key → i18n (32 §5.1).",
  },
];

const restrictedImportPatterns = {
  lucideDynamic: {
    group: ["lucide-react/dynamic", "lucide-react/dynamicIconImports"],
    message: "DynamicIcon / nom bo'yicha runtime qidiruv taqiqlangan — butun to'plam bundle'ga tushadi (24 §4.2).",
  },
  otherPages: {
    group: ["@pages/*"],
    message: "Sahifa paketlari bir-birini import qilmaydi; paketlararo faqat @shared/* (24 §1).",
  },
  appShell: {
    group: ["shell", "shell/*"],
    message: "Paketlar ilova qobig'ini (apps/shell) import qilmaydi (24 §1).",
  },
  deepShared: {
    group: ["@shared/*/src/*", "**/packages/shared/**"],
    message: "@shared paketlariga faqat ularning eksport yo'li orqali murojaat qiling.",
  },
};

/** FSD layers inside a package: app → pages → features → entities → shared (24 §1). */
const fsdElements = [
  { type: "app", pattern: ["src/app"] },
  { type: "pages", pattern: ["src/pages/*"], capture: ["page"] },
  { type: "features", pattern: ["src/features/*"], capture: ["feature"] },
  { type: "entities", pattern: ["src/entities/*"], capture: ["entity"] },
  { type: "shared", pattern: ["src/shared"] },
];

const layers = (types) => ({ to: { element: { types: { anyOf: types } } } });
const sameSlice = (type, key) => ({
  to: { element: { type, captured: { [key]: `{{ from.element.captured.${key} }}` } } },
});

const fsdPolicies = [
  // Third-party and workspace packages (@shared/*) are governed by no-restricted-imports, not FSD.
  { allow: [{ to: { module: { origin: "external" } } }, { to: { module: { origin: "core" } } }] },
  { from: { element: { type: "app" } }, allow: layers(["app", "pages", "features", "entities", "shared"]) },
  // A page may use its own files, features, entities and shared — never another page.
  { from: { element: { type: "pages" } }, allow: [sameSlice("pages", "page"), layers(["features", "entities", "shared"])] },
  { from: { element: { type: "features" } }, allow: [sameSlice("features", "feature"), layers(["entities", "shared"])] },
  { from: { element: { type: "entities" } }, allow: [sameSlice("entities", "entity"), layers(["shared"])] },
  { from: { element: { type: "shared" } }, allow: layers(["shared"]) },
];

/**
 * @param {{ tsconfigRootDir: string, kind: "app" | "pages" | "shared" | "config", ignores?: string[], projects?: string[] }} options
 *   `projects` — explicit tsconfig files when a package has several (e.g. app + node configs);
 *   otherwise the TypeScript project service picks the nearest tsconfig.json.
 */
export function createConfig({ tsconfigRootDir, kind, ignores = [], projects }) {
  const forbidden = [restrictedImportPatterns.lucideDynamic, restrictedImportPatterns.deepShared];
  if (kind === "pages") forbidden.push(restrictedImportPatterns.otherPages, restrictedImportPatterns.appShell);
  if (kind === "shared") forbidden.push(restrictedImportPatterns.otherPages, restrictedImportPatterns.appShell);

  return tseslint.config(
    {
      ignores: [
        "dist/**",
        "dev-dist/**",
        "coverage/**",
        "node_modules/**",
        "**/generated/**",
        "playwright-report/**",
        "test-results/**",
        ...ignores,
      ],
    },
    js.configs.recommended,
    ...tseslint.configs.recommendedTypeChecked,
    {
      languageOptions: {
        ecmaVersion: 2023,
        sourceType: "module",
        globals: { ...globals.browser },
        parserOptions: projects ? { project: projects, tsconfigRootDir } : { projectService: true, tsconfigRootDir },
      },
      plugins: { erp: erpPlugin, "react-hooks": reactHooks },
      rules: {
        ...reactHooks.configs.recommended.rules,
        "no-console": ["error", { allow: ["warn", "error"] }],
        "no-restricted-syntax": ["error", ...moneyRestrictedSyntax],
        // qaror #57 / 32 §3.3: unary `+amount` is a hidden Number() — money/qty stay decimal strings.
        "no-implicit-coercion": ["error", { boolean: false, number: true, string: false }],
        "no-restricted-imports": ["error", { patterns: forbidden }],
        "erp/no-money-arithmetic": "error",
        "erp/lucide-via-icon": "error",
        "@typescript-eslint/no-explicit-any": "error",
        "@typescript-eslint/consistent-type-imports": ["error", { fixStyle: "separate-type-imports" }],
        "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
        "@typescript-eslint/no-misused-promises": ["error", { checksVoidReturn: { attributes: false } }],
        // Effector `sample`/effects return values legitimately ignored in connections/.
        "@typescript-eslint/no-floating-promises": ["error", { ignoreVoid: true }],
      },
    },
    kind === "pages" || kind === "app"
      ? {
          files: ["src/**/*.{ts,tsx}"],
          plugins: { boundaries },
          settings: {
            "boundaries/elements": fsdElements,
            "boundaries/include": ["src/**/*"],
            "import/resolver": { typescript: { project: `${tsconfigRootDir}/tsconfig.json` } },
          },
          rules: {
            "boundaries/dependencies": ["error", { default: "disallow", policies: fsdPolicies }],
          },
        }
      : {},
    {
      // Config files, scripts and tests run in Node.
      files: ["*.config.{js,ts,mjs}", "scripts/**", "e2e/**", "dev/**", "**/*.test.{ts,tsx}"],
      languageOptions: { globals: { ...globals.node, ...globals.browser } },
    },
    {
      files: ["**/*.js", "**/*.mjs"],
      ...tseslint.configs.disableTypeChecked,
      rules: { ...tseslint.configs.disableTypeChecked.rules, "erp/no-money-arithmetic": "off" },
    },
  );
}

export default createConfig;
