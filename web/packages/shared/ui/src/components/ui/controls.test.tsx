import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { CheckboxList, MultiSelect } from "../../composites/multi-select.tsx";
import { ErrorState, NoPermissionState } from "../../composites/states.tsx";
import { Label } from "./label.tsx";

import { Checkbox } from "./checkbox.tsx";
import { RadioCard, RadioGroup } from "./radio-group.tsx";
import { SimpleSelect } from "./select.tsx";
import { Switch } from "./switch.tsx";
import { Textarea } from "./textarea.tsx";
import { SimpleTooltip } from "./tooltip.tsx";

const LEGAL_FORMS = [
  { value: "llc", title: "MChJ", description: "Mas'uliyati cheklangan jamiyat" },
  { value: "jsc", title: "AJ", description: "Aksiyadorlik jamiyati" },
  { value: "sole_proprietor", title: "Yakka tadbirkor", description: "YaTT" },
];

describe("Checkbox / Switch / Textarea", () => {
  it("checkbox toggles through its label", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <div>
        <Checkbox id="terms" onCheckedChange={onChange} />
        <Label htmlFor="terms">Roziman</Label>
      </div>,
    );
    await user.click(screen.getByText("Roziman"));
    expect(screen.getByRole("checkbox", { name: "Roziman" })).toBeChecked();
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("switch exposes role=switch and toggles with Space", async () => {
    const user = userEvent.setup();
    render(<Switch aria-label="AI rozilik" />);
    const sw = screen.getByRole("switch", { name: "AI rozilik" });
    expect(sw).not.toBeChecked();
    sw.focus();
    await user.keyboard(" ");
    expect(sw).toBeChecked();
  });

  it("textarea forwards aria-invalid", () => {
    render(<Textarea aria-label="Izoh" aria-invalid />);
    expect(screen.getByRole("textbox", { name: "Izoh" })).toHaveAttribute("aria-invalid", "true");
  });
});

describe("RadioGroup + RadioCard — BO-21 legal form", () => {
  it("selects by click and moves with arrow keys", async () => {
    const user = userEvent.setup();
    function Harness() {
      const [v, setV] = useState("llc");
      return (
        <RadioGroup
          aria-label="Tashkiliy-huquqiy shakl"
          value={v}
          onValueChange={setV}
          className="grid-cols-3"
        >
          {LEGAL_FORMS.map((f) => (
            <RadioCard key={f.value} value={f.value} title={f.title} description={f.description} />
          ))}
        </RadioGroup>
      );
    }
    render(<Harness />);
    expect(screen.getByRole("radiogroup", { name: "Tashkiliy-huquqiy shakl" })).toBeInTheDocument();
    const llc = screen.getByRole("radio", { name: /MChJ/ });
    expect(llc).toBeChecked();
    await user.click(screen.getByRole("radio", { name: /AJ/ }));
    expect(screen.getByRole("radio", { name: /AJ/ })).toBeChecked();
    await user.keyboard("{ArrowRight}");
    const sole = screen.getByRole("radio", { name: /Yakka tadbirkor/ });
    expect(sole).toHaveFocus();
    await user.keyboard(" ");
    expect(sole).toBeChecked();
  });
});

describe("SimpleSelect", () => {
  it("opens, picks an option and reports the value", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(
      <SimpleSelect
        aria-label="Faoliyat turi"
        value={undefined}
        onValueChange={onValueChange}
        options={[
          { value: "grocery", label: "Oziq-ovqat" },
          { value: "pharmacy", label: "Dorixona" },
        ]}
      />,
    );
    const trigger = screen.getByRole("combobox", { name: "Faoliyat turi" });
    expect(trigger).toHaveTextContent("Tanlang");
    await user.click(trigger);
    await user.click(await screen.findByRole("option", { name: "Dorixona" }));
    expect(onValueChange).toHaveBeenCalledWith("pharmacy");
  });
});

describe("CheckboxList / MultiSelect — roles, branches", () => {
  const options = [
    { value: "b1", label: "Chilonzor-3" },
    { value: "b2", label: "Yunusobod-1" },
    { value: "b3", label: "Sergeli", disabled: true },
  ];

  function Harness({ multi = false }: { multi?: boolean }) {
    const [v, setV] = useState<string[]>([]);
    return multi ? (
      <MultiSelect
        legend="Filiallar"
        options={options}
        value={v}
        onChange={setV}
        selectAll
        aria-invalid={false}
      />
    ) : (
      <>
        <CheckboxList legend="Filiallar" options={options} value={v} onChange={setV} selectAll />
        <output>{v.join(",")}</output>
      </>
    );
  }

  it("is a labelled group; select-all skips disabled options and becomes indeterminate", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    expect(screen.getByRole("group", { name: "Filiallar" })).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Yunusobod-1" }));
    expect(screen.getByRole("status")).toHaveTextContent("b2");
    expect(screen.getByRole("checkbox", { name: "Hammasi" })).toHaveAttribute("aria-checked", "mixed");
    await user.click(screen.getByRole("checkbox", { name: "Hammasi" }));
    expect(screen.getByRole("status")).toHaveTextContent("b1,b2");
    await user.click(screen.getByRole("checkbox", { name: "Hammasi" }));
    expect(screen.getByRole("status")).toHaveTextContent("");
  });

  it("MultiSelect summarises the choice in its trigger", async () => {
    const user = userEvent.setup();
    render(<Harness multi />);
    const trigger = screen.getByRole("button", { name: "Tanlang" });
    await user.click(trigger);
    await user.click(await screen.findByRole("checkbox", { name: "Chilonzor-3" }));
    await user.click(screen.getByRole("checkbox", { name: "Yunusobod-1" }));
    await waitFor(() => expect(trigger).toHaveTextContent("Chilonzor-3, Yunusobod-1"));
  });
});

describe("states", () => {
  it("ErrorState is an alert with a retry button", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<ErrorState message="Server bilan aloqa yo'q" onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Ma'lumotni yuklab bo'lmadi");
    await user.click(screen.getByRole("button", { name: "Qayta urinish" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("NoPermissionState shows the standard text", () => {
    render(<NoPermissionState />);
    expect(screen.getByText("Sizda bu bo'limga kirish huquqi yo'q")).toBeInTheDocument();
  });
});

describe("SimpleTooltip", () => {
  it("shows the hint on keyboard focus", async () => {
    const user = userEvent.setup();
    render(
      <SimpleTooltip content="Faqat Egasi o'zgartira oladi">
        <button type="button">Rol</button>
      </SimpleTooltip>,
    );
    await user.tab();
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Faqat Egasi o'zgartira oladi");
  });
});
