/**
 * erp/no-money-arithmetic — qaror #57, 32-kod-qoidalari.md §3.3, 24 §4.
 *
 * Forbids `+ - * / %` (and their compound assignments, unary minus, ++/--) on any operand whose
 * static type is the branded `Money` type from `@shared/lib/money`. Money is a decimal string
 * ("12000.00"); arithmetic is allowed only through the decimal.js helpers inside shared/lib/money,
 * which opt out with an eslint-disable comment.
 *
 * Type-aware: needs `parserOptions.projectService`. A type counts as Money when it (or a member of a
 * union/intersection) carries the brand property `__brand` whose type is the string literal "Money".
 */
import { ESLintUtils } from "@typescript-eslint/utils";

const ARITHMETIC = new Set(["+", "-", "*", "/", "%", "**"]);
const ASSIGNMENT = new Set(["+=", "-=", "*=", "/=", "%=", "**="]);

/** @param {import("typescript").Type} type @param {import("typescript").TypeChecker} checker */
function isMoneyType(type, checker, depth = 0) {
  if (!type || depth > 4) return false;
  if (type.isUnionOrIntersection()) {
    return type.types.some((t) => isMoneyType(t, checker, depth + 1));
  }
  if (type.aliasSymbol && type.aliasSymbol.getName() === "Money") return true;
  const brand = type.getProperty("__brand");
  if (!brand) return false;
  const brandType = checker.getTypeOfSymbol(brand);
  return brandType.isStringLiteral() && brandType.value === "Money";
}

export const noMoneyArithmetic = ESLintUtils.RuleCreator.withoutDocs({
  meta: {
    type: "problem",
    schema: [],
    messages: {
      moneyArithmetic:
        "Pul (Money) qiymati ustida '{{op}}' amali taqiqlangan — @shared/lib/money (decimal.js) funksiyalaridan foydalaning (qaror #57).",
    },
  },
  defaultOptions: [],
  create(context) {
    const services = ESLintUtils.getParserServices(context);
    const checker = services.program.getTypeChecker();
    const isMoney = (node) => isMoneyType(services.getTypeAtLocation(node), checker);

    return {
      BinaryExpression(node) {
        if (!ARITHMETIC.has(node.operator)) return;
        if (node.left.type === "PrivateIdentifier") return;
        if (isMoney(node.left) || isMoney(node.right)) {
          context.report({ node, messageId: "moneyArithmetic", data: { op: node.operator } });
        }
      },
      AssignmentExpression(node) {
        if (!ASSIGNMENT.has(node.operator)) return;
        if (isMoney(node.left) || isMoney(node.right)) {
          context.report({ node, messageId: "moneyArithmetic", data: { op: node.operator } });
        }
      },
      UnaryExpression(node) {
        if ((node.operator === "-" || node.operator === "+") && isMoney(node.argument)) {
          context.report({ node, messageId: "moneyArithmetic", data: { op: node.operator } });
        }
      },
      UpdateExpression(node) {
        if (isMoney(node.argument)) {
          context.report({ node, messageId: "moneyArithmetic", data: { op: node.operator } });
        }
      },
    };
  },
});
