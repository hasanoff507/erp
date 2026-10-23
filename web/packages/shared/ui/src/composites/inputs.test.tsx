import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { FileDropzone } from "./file-dropzone.tsx";
import { MoneyInput, PriceInput } from "./money-input.tsx";
import { OtpInput } from "./otp-input.tsx";
import { PasswordInput } from "./password-input.tsx";
import { PhoneInput } from "./phone-input.tsx";
import { SearchInput } from "./search-input.tsx";
import { StepList, StepProgress } from "./step-list.tsx";

const NBSP = " ";

describe("PhoneInput — +998 XX XXX XX XX", () => {
  function Harness({ initial = "" }: { initial?: string }) {
    const [v, setV] = useState(initial);
    return (
      <>
        <PhoneInput aria-label="Telefon" value={v} onChange={setV} />
        <output>{v}</output>
      </>
    );
  }

  it("masks while typing and emits national digits", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByRole("textbox", { name: "Telefon" });
    expect(input).toHaveAttribute("type", "tel");
    await user.type(input, "901234567");
    expect(input).toHaveValue("90 123 45 67");
    expect(screen.getByRole("status")).toHaveTextContent("901234567");
  });

  it("accepts a pasted international number and E.164 values", async () => {
    const user = userEvent.setup();
    render(<Harness initial="+998935554433" />);
    const input = screen.getByRole("textbox", { name: "Telefon" });
    expect(input).toHaveValue("93 555 44 33");
    await user.clear(input);
    await user.paste("+998 90 123 45 67");
    expect(input).toHaveValue("90 123 45 67");
  });
});

describe("OtpInput — 6 digits", () => {
  function Harness({ onComplete }: { onComplete: (v: string) => void }) {
    const [v, setV] = useState("");
    return <OtpInput value={v} onChange={setV} onComplete={onComplete} />;
  }

  it("types digit by digit, moves focus and completes", async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);
    expect(screen.getByRole("group", { name: "Tasdiqlash kodi" })).toBeInTheDocument();
    const boxes = screen.getAllByRole("textbox");
    expect(boxes).toHaveLength(6);
    expect(boxes[0]).toHaveAttribute("autocomplete", "one-time-code");
    expect(boxes[0]).toHaveAccessibleName("1-raqam");
    await user.click(boxes[0] as HTMLElement);
    await user.keyboard("12a3456");
    expect(boxes.map((b) => (b as HTMLInputElement).value).join("")).toBe("123456");
    expect(onComplete).toHaveBeenCalledWith("123456");
  });

  it("pastes the whole code and Backspace walks back", async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);
    const boxes = screen.getAllByRole("textbox");
    await user.click(boxes[0] as HTMLElement);
    await user.paste("Kod: 654 321");
    expect(onComplete).toHaveBeenCalledWith("654321");
    await user.click(boxes[5] as HTMLElement);
    await user.keyboard("{Backspace}{Backspace}");
    expect(boxes.map((b) => (b as HTMLInputElement).value).join("")).toBe("6543");
    expect(boxes[4]).toHaveFocus();
  });
});

describe("PasswordInput", () => {
  it("toggles visibility with an accessible pressed button", async () => {
    const user = userEvent.setup();
    render(<PasswordInput aria-label="Parol" defaultValue="sir" />);
    const input = screen.getByLabelText("Parol");
    expect(input).toHaveAttribute("type", "password");
    const toggle = screen.getByRole("button", { name: "Parolni ko'rsatish" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.click(toggle);
    expect(input).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Parolni yashirish" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("MoneyInput / PriceInput — decimal strings only", () => {
  function Harness({ initial = "", price = false }: { initial?: string; price?: boolean }) {
    const [v, setV] = useState(initial);
    return (
      <>
        {price ? (
          <PriceInput aria-label="Tannarx" value={v} onChange={setV} />
        ) : (
          <MoneyInput aria-label="Narx" value={v} onChange={setV} />
        )}
        <output>{v}</output>
        <button type="button" onClick={() => setV("")}>
          reset
        </button>
      </>
    );
  }

  it("groups whole so'm, shows the suffix and emits a 2-place string", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByRole("textbox", { name: "Narx" });
    expect(input).toHaveAttribute("inputmode", "numeric");
    expect(screen.getByText("so'm")).toBeInTheDocument();
    await user.type(input, "1240000");
    expect(input).toHaveValue(`1${NBSP}240${NBSP}000`);
    expect(screen.getByRole("status")).toHaveTextContent("1240000.00");
    // Whole so'm: separators and letters are ignored.
    await user.type(input, ",x");
    expect(input).toHaveValue(`1${NBSP}240${NBSP}000`);
    expect(screen.getByRole("status")).toHaveTextContent("1240000.00");
  });

  it("adopts external values and resets", async () => {
    const user = userEvent.setup();
    render(<Harness initial="99000.00" />);
    const input = screen.getByRole("textbox", { name: "Narx" });
    expect(input).toHaveValue(`99${NBSP}000`);
    await user.click(screen.getByRole("button", { name: "reset" }));
    expect(input).toHaveValue("");
  });

  it("price keeps up to 4 decimals typed with a comma", async () => {
    const user = userEvent.setup();
    render(<Harness price />);
    const input = screen.getByRole("textbox", { name: "Tannarx" });
    expect(input).toHaveAttribute("inputmode", "decimal");
    await user.type(input, "8333,33339");
    expect(input).toHaveValue(`8${NBSP}333,3333`);
    expect(screen.getByRole("status")).toHaveTextContent("8333.3333");
  });

  it("keeps the caret on the same digit after regrouping", () => {
    render(<Harness initial="1234.00" />);
    const input = screen.getByRole<HTMLInputElement>("textbox", { name: "Narx" });
    input.focus();
    // User inserts "5" after "1 2" → raw "1 2534" with the caret after the 5.
    fireEvent.change(input, { target: { value: `1${NBSP}2534`, selectionStart: 4, selectionEnd: 4 } });
    expect(input).toHaveValue(`12${NBSP}534`);
    expect(input.selectionStart).toBe(4);
  });
});

describe("SearchInput — debounce", () => {
  it("fires once after the pause, immediately on Enter and with '' on Esc", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(<SearchInput onSearch={onSearch} delay={150} />);
    const box = screen.getByRole("searchbox", { name: "Qidiruv" });
    await user.type(box, "non");
    expect(onSearch).not.toHaveBeenCalled();
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1));
    expect(onSearch).toHaveBeenLastCalledWith("non");
    await user.type(box, " sut{Enter}");
    expect(onSearch).toHaveBeenLastCalledWith("non sut");
    await user.keyboard("{Escape}");
    expect(onSearch).toHaveBeenLastCalledWith("");
    expect(box).toHaveValue("");
  });

  it("respects minLength and the clear button", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(<SearchInput onSearch={onSearch} minLength={3} aria-label="MXIK" />);
    const box = screen.getByRole("searchbox", { name: "MXIK" });
    await user.type(box, "ab{Enter}");
    expect(onSearch).not.toHaveBeenCalled();
    await user.type(box, "c{Enter}");
    expect(onSearch).toHaveBeenLastCalledWith("abc");
    await user.click(screen.getByRole("button", { name: "Qidiruvni tozalash" }));
    expect(onSearch).toHaveBeenLastCalledWith("");
  });
});

describe("FileDropzone — xlsx/csv ≤ 10 MB", () => {
  const csv = (size = 10) => new File(["x".repeat(size)], "Tovarlar.csv", { type: "text/csv" });

  it("accepts a valid file via the keyboard-reachable picker", async () => {
    const user = userEvent.setup();
    const onFile = vi.fn();
    const { container } = render(<FileDropzone onFile={onFile} />);
    expect(screen.getByText("XLSX, CSV · 10 MB gacha")).toBeInTheDocument();
    const browse = screen.getByRole("button", { name: "Fayl tanlash" });
    await user.tab();
    expect(browse).toHaveFocus();
    const input = container.querySelector<HTMLInputElement>('input[type="file"]');
    await user.upload(input as HTMLInputElement, csv());
    expect(onFile).toHaveBeenCalledWith(expect.objectContaining({ name: "Tovarlar.csv" }));
  });

  it("rejects a wrong type and an oversized file with translated errors", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();
    const { container } = render(<FileDropzone onFile={onFile} onReject={onReject} maxSize={5} />);
    const zone = container.querySelector("[class*='border-dashed']") as HTMLElement;
    fireEvent.drop(zone, {
      dataTransfer: { files: [new File(["%PDF"], "a.pdf", { type: "application/pdf" })] },
    });
    expect(screen.getByRole("alert")).toHaveTextContent("Faqat XLSX, CSV fayllari qabul qilinadi");
    expect(onReject).toHaveBeenLastCalledWith("wrong_type", expect.any(File));
    fireEvent.drop(zone, { dataTransfer: { files: [csv(10)] } });
    expect(screen.getByRole("alert")).toHaveTextContent("Fayl hajmi 5 B dan oshmasin");
    expect(onReject).toHaveBeenLastCalledWith("too_large", expect.any(File));
    expect(onFile).not.toHaveBeenCalled();
  });

  it("shows the selected file and a remove button; server errors are translated", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();
    render(
      <FileDropzone
        onFile={vi.fn()}
        file={csv(1536)}
        onRemove={onRemove}
        error="errors.import_file_invalid"
      />,
    );
    expect(screen.getByText("Tovarlar.csv")).toBeInTheDocument();
    expect(screen.getByText("1,5 KB")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Fayl formati yoki kodlashi noto'g'ri");
    await user.click(screen.getByRole("button", { name: "Faylni olib tashlash" }));
    expect(onRemove).toHaveBeenCalledOnce();
  });
});

describe("StepList / StepProgress — BO-21", () => {
  const steps = [
    {
      id: "account",
      title: "Telefon+parol yoki Google",
      description: "Kod, parol, ism",
      state: "done" as const,
    },
    { id: "store", title: "Do'kon", description: "Nom, faoliyat turi", state: "current" as const },
    { id: "products", title: "Tovarlar/Qoldiq", state: "next" as const },
    { id: "debts", title: "Boshlang'ich qarzlar", state: "optional" as const },
  ];

  it("marks the current step and announces each state", async () => {
    const user = userEvent.setup();
    const onStepClick = vi.fn();
    render(<StepList steps={steps} onStepClick={onStepClick} />);
    const list = screen.getByRole("list", { name: "Bosqichlar" });
    const items = list.querySelectorAll("li");
    expect(items[1]).toHaveAttribute("aria-current", "step");
    expect(items[0]).toHaveTextContent("Kod, parol, ism · bajarildi");
    expect(items[1]).toHaveTextContent("joriy");
    expect(items[3]).toHaveTextContent("ixtiyoriy");
    await user.click(screen.getByRole("button", { name: /Telefon\+parol/ }));
    expect(onStepClick).toHaveBeenCalledWith("account");
  });

  it("shows 'N-bosqich / 6' and a progressbar", () => {
    render(<StepProgress current={2} total={6} label="Ro'yxatdan o'tish jarayoni" />);
    expect(screen.getByText("2-bosqich / 6")).toBeInTheDocument();
    const bar = screen.getByRole("progressbar", { name: "Ro'yxatdan o'tish jarayoni" });
    expect(bar).toHaveAttribute("aria-valuenow", "2");
    expect(bar).toHaveAttribute("aria-valuemax", "6");
  });
});
