/**
 * @shared/ui/form — react-hook-form + zod wiring (24 §4: "forma — react-hook-form + zod").
 * Pages import everything form-related from here (no direct react-hook-form/zod dependency needed):
 *
 *   import { RhfField, useZodForm, z, zPhone, applyApiErrorToForm } from "@shared/ui/form";
 *   const schema = z.object({ name: z.string().trim().min(1).max(100), phone: zPhone() });
 *   const form = useZodForm(schema, { defaultValues: { name: "", phone: "" } });
 *
 * Messages are i18n KEYS (08 §11: `validation.*`), installed globally through `z.config`; the
 * FormField component translates them. Server `details[]` reuse the same keys (17 §7.1).
 */
export { z } from "zod";
export {
  Controller,
  FormProvider,
  useFieldArray,
  useFormContext,
  useWatch,
  type Control,
  type FieldPath,
  type FieldValues,
  type SubmitHandler,
  type UseFormReturn,
} from "react-hook-form";

export {
  installZodErrorMap,
  zDecimal,
  zEan,
  zOtp,
  zPhone,
  zRequiredString,
  type ZDecimalOptions,
} from "./schema.ts";
export { applyApiErrorToForm, RhfField, useZodForm, type RhfFieldProps } from "./rhf.tsx";
