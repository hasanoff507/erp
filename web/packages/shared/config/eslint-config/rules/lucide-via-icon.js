/**
 * erp/lucide-via-icon — 24-frontend-arxitekturasi.md §4.2.
 *
 * lucide-react icons are imported by name (tree-shaking) but rendered only through the shared
 * `<Icon as={ScanLine} />` wrapper (strokeWidth 1.8, aria-hidden). Rendering `<ScanLine />` directly
 * as JSX is reported. Passing the component reference as a value (`as={ScanLine}`, menu arrays) is fine.
 */
export const lucideViaIcon = {
  meta: {
    type: "problem",
    schema: [],
    messages: {
      direct:
        "lucide ikonkasi '{{name}}' to'g'ridan-to'g'ri chizilmaydi — @shared/ui Icon o'rami orqali: <Icon as={X} />, X = {{name}} (24 §4.2).",
    },
  },
  create(context) {
    const lucideNames = new Set();
    return {
      ImportDeclaration(node) {
        if (node.source.value !== "lucide-react") return;
        for (const spec of node.specifiers) {
          if (spec.type === "ImportSpecifier") lucideNames.add(spec.local.name);
        }
      },
      JSXOpeningElement(node) {
        if (node.name.type === "JSXIdentifier" && lucideNames.has(node.name.name)) {
          context.report({ node, messageId: "direct", data: { name: node.name.name } });
        }
      },
    };
  },
};
