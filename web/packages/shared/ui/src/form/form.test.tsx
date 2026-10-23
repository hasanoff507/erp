import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@shared/api";

import { FormField, translateFieldError, withParams } from "../composites/form-field.tsx";
import { PhoneInput } from "../composites/phone-input.tsx";
import { MoneyInput } from "../composites/money-input.tsx";
import { Input } from "../components/ui/input.tsx";

import {
  applyApiErrorToForm,
  RhfField,
  useZodForm,
  z,
  zDecimal,
  zEan,
  zOtp,
  zPhone,
  zRequiredString,
} from "./index.ts";

describe("FormField — label / hint / error / required", () => {
  it("wires id, aria-describedby, aria-invalid and aria-required to a cloned child", () => {
    render(
      <FormField label="Do'kon nomi" required hint="2–100 belgi" error="validation.required">
        <Input />
      </FormField>,
    );
    const input = screen.getByRole("textbox", { name: /Do'kon nomi/ });
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-required", "true");
    expect(input).toHaveAccessibleDescription("Bu maydonni to'ldirish shart 2–100 belgi");
    expect(screen.getByRole("alert")).toHaveTextContent("Bu maydonni to'ldirish shart");
  });

  it("render-prop form and optional mark; no error → no alert", () => {
    render(
      <FormField label="AI rozilik" optional>
        {(a11y) => <input {...a11y} />}
      </FormField>,
    );
    expect(screen.getByText(/ixtiyoriy/)).toBeInTheDocument();
    expect(screen.getByRole("textbox")).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("translates keys with params, falls back for unknown keys, passes plain text through", () => {
    expect(translateFieldError(withParams("validation.min_length", { min: 2 }))).toBe(
      "Kamida 2 ta belgi kiriting",
    );
    expect(translateFieldError("errors.barcode_duplicate")).toBe("Bu shtrix-kod boshqa tovarda bor");
    expect(translateFieldError("validation.no_such_key")).toBe("Format mos kelmadi — tekshirib ko'ring");
    expect(translateFieldError("Tayyor matn")).toBe("Tayyor matn");
    expect(translateFieldError(undefined)).toBeNull();
  });
});

describe("zod → validation.* keys (08 §11)", () => {
  const issue = (schema: z.ZodType, value: unknown) => schema.safeParse(value).error?.issues[0]?.message;

  it("maps the built-in checks", () => {
    expect(issue(z.string().min(1), "")).toBe("validation.required");
    expect(issue(z.string(), undefined)).toBe("validation.required");
    expect(issue(z.string().min(2), "a")).toBe("validation.min_length?min=2");
    expect(issue(z.string().max(3), "abcd")).toBe("validation.max_length");
    expect(issue(z.email(), "x")).toBe("validation.email_format");
    expect(issue(z.enum(["llc", "jsc"]), "x")).toBe("validation.invalid_choice");
    expect(issue(z.array(z.string()).min(1), [])).toBe("validation.required");
    expect(issue(z.string().min(1, { message: "validation.terms_required" }), "")).toBe(
      "validation.terms_required",
    );
  });

  it("domain helpers", () => {
    expect(issue(zRequiredString(5), "   ")).toBe("validation.required");
    expect(issue(zPhone(), "90 123")).toBe("validation.phone_format");
    expect(zPhone().safeParse("901234567").success).toBe(true);
    expect(issue(zOtp(), "12345")).toBe("validation.otp_length");
    expect(zOtp().safeParse("123456").success).toBe(true);
    expect(issue(zEan(), "4601234567890")).toBe("validation.barcode_check_digit");
    expect(zEan().safeParse("4601234567893").success).toBe(true);
  });

  it("zDecimal validates decimal strings without Number()", () => {
    const price = zDecimal({ scale: 2, positive: true });
    expect(price.safeParse("12000.00").success).toBe(true);
    expect(issue(price, "")).toBe("validation.required");
    expect(issue(price, "0.00")).toBe("validation.must_be_positive");
    expect(issue(price, "1.234")).toBe("validation.decimal_format");
    expect(issue(price, "1e3")).toBe("validation.decimal_format");
    expect(zDecimal({ scale: 2, optional: true }).safeParse("").success).toBe(true);
    expect(zDecimal({ scale: 0, allowNegative: true }).safeParse("-5").success).toBe(true);
  });
});

const schema = z.object({
  name: zRequiredString(100),
  phone: zPhone(),
  price: zDecimal({ scale: 2, positive: true }),
});

function StaffForm({
  onSubmit,
  serverError,
}: {
  onSubmit: (v: z.output<typeof schema>) => void;
  serverError?: ApiError;
}) {
  const form = useZodForm(schema, { defaultValues: { name: "", phone: "", price: "" } });
  return (
    <form
      noValidate
      onSubmit={(e) =>
        void form.handleSubmit((values) => {
          if (serverError) applyApiErrorToForm(form, serverError);
          else onSubmit(values);
        })(e)
      }
    >
      <RhfField
        control={form.control}
        name="name"
        label="To'liq ism"
        required
        render={({ field, control }) => <Input {...control} {...field} />}
      />
      <RhfField
        control={form.control}
        name="phone"
        label="Telefon"
        required
        render={({ field, control }) => <PhoneInput {...control} {...field} />}
      />
      <RhfField
        control={form.control}
        name="price"
        label="Narx"
        required
        render={({ field, control }) => <MoneyInput {...control} {...field} />}
      />
      <button type="submit">Saqlash</button>
    </form>
  );
}

describe("RhfField + useZodForm", () => {
  it("shows translated errors on submit and submits decimal strings", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<StaffForm onSubmit={onSubmit} />);
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(await screen.findAllByText("Bu maydonni to'ldirish shart")).toHaveLength(2);
    expect(screen.getByText("Telefon raqami formatiga mos emas")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /To'liq ism/ })).toHaveFocus();

    await user.type(screen.getByRole("textbox", { name: /To'liq ism/ }), "Dilnoza Rahimova");
    await user.type(screen.getByRole("textbox", { name: /Telefon/ }), "901234567");
    await user.type(screen.getByRole("textbox", { name: /Narx/ }), "12000");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        name: "Dilnoza Rahimova",
        phone: "901234567",
        price: "12000.00",
      }),
    );
  });

  it("applyApiErrorToForm puts server details on the matching fields", async () => {
    const user = userEvent.setup();
    const serverError = new ApiError({
      status: 422,
      code: "VALIDATION_ERROR",
      messageKey: "errors.validation",
      details: [
        { field: "phone", messageKey: "validation.phone_format" },
        { field: "body.name", messageKey: "validation.max_length" },
        { field: "Idempotency-Key", messageKey: "validation.required" },
      ],
    });
    render(<StaffForm onSubmit={vi.fn()} serverError={serverError} />);
    await user.type(screen.getByRole("textbox", { name: /To'liq ism/ }), "Dilnoza");
    await user.type(screen.getByRole("textbox", { name: /Telefon/ }), "901234567");
    await user.type(screen.getByRole("textbox", { name: /Narx/ }), "5");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));
    expect(await screen.findByText("Ruxsat etilgan uzunlikdan oshdi")).toBeInTheDocument();
    expect(screen.getByText("Telefon raqami formatiga mos emas")).toBeInTheDocument();
  });
});
