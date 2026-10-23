/**
 * @shared/ui — shadcn/ui components (components/ui) + project composites (08 §7.2),
 * themed by styles/theme.css tokens through the Tailwind preset (24 §4.3).
 * Styles entry: import "@shared/ui/styles.css" once in the app.
 */
export { cn } from "./lib/cn.ts";
export { Icon, ICON_SIZES, type IconProps, type IconSize, type LucideIcon } from "./icon/Icon.tsx";

export { Button, buttonVariants, type ButtonProps } from "./components/ui/button.tsx";
export { Input, inputClassName, type InputProps } from "./components/ui/input.tsx";
export { Label } from "./components/ui/label.tsx";
export { Card, CardTitle } from "./components/ui/card.tsx";
export { Skeleton } from "./components/ui/skeleton.tsx";
export {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./components/ui/dropdown-menu.tsx";

export { type Tone } from "./composites/tone.ts";
export { Kbd, type KbdProps } from "./composites/kbd.tsx";
export { StatusChip, type StatusChipProps } from "./composites/status-chip.tsx";
export {
  SegmentedControl,
  type SegmentedControlProps,
  type SegmentedOption,
} from "./composites/segmented-control.tsx";
export { KpiCard, type KpiCardProps } from "./composites/kpi-card.tsx";
export { Banner, EmptyState, type BannerProps, type EmptyStateProps } from "./composites/states.tsx";
export { Avatar, LogoMark, initialsOf } from "./composites/identity.tsx";
export { NativeSelect, type NativeSelectOption } from "./composites/native-select.tsx";

// --- Bosqich 1 foundation (W0): overlays, form controls, data display ---------------------------
export { Textarea, type TextareaProps } from "./components/ui/textarea.tsx";
export { Checkbox } from "./components/ui/checkbox.tsx";
export { RadioCard, RadioGroup, RadioGroupItem, type RadioCardProps } from "./components/ui/radio-group.tsx";
export { Switch } from "./components/ui/switch.tsx";
export {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
  SimpleSelect,
  type SelectOption,
  type SimpleSelectProps,
} from "./components/ui/select.tsx";
export { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs.tsx";
export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  type DialogContentProps,
} from "./components/ui/dialog.tsx";
export {
  Sheet,
  SheetBody,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  type SheetContentProps,
} from "./components/ui/sheet.tsx";
export { Popover, PopoverAnchor, PopoverContent, PopoverTrigger } from "./components/ui/popover.tsx";
export {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandLoading,
  CommandSeparator,
  CommandShortcut,
  type CommandDialogProps,
} from "./components/ui/command.tsx";
export {
  SimpleTooltip,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
  type SimpleTooltipProps,
} from "./components/ui/tooltip.tsx";
export { Toaster, toast, type ToastOptions, type ToastTone } from "./components/ui/toast.tsx";

export { ConfirmDialog, type ConfirmDialogProps } from "./composites/confirm-dialog.tsx";
export { ErrorState, NoPermissionState, type ErrorStateProps } from "./composites/states.tsx";
export {
  DataTable,
  type DataTableColumn,
  type DataTablePagination,
  type DataTableProps,
  type DataTableRowAction,
  type DataTableStatus,
} from "./composites/data-table.tsx";
export {
  FormField,
  translateFieldError,
  withParams,
  type FieldControlProps,
  type FormFieldProps,
} from "./composites/form-field.tsx";
export { PhoneInput, type PhoneInputProps } from "./composites/phone-input.tsx";
export { OtpInput, type OtpInputProps } from "./composites/otp-input.tsx";
export { PasswordInput, type PasswordInputProps } from "./composites/password-input.tsx";
export {
  DecimalInput,
  MoneyInput,
  PriceInput,
  type DecimalInputProps,
  type MoneyInputProps,
  type PriceInputProps,
} from "./composites/money-input.tsx";
export { SearchInput, type SearchInputProps } from "./composites/search-input.tsx";
export { FileDropzone, type FileDropzoneProps, type FileRejectReason } from "./composites/file-dropzone.tsx";
export {
  StepList,
  StepProgress,
  type StepItem,
  type StepListProps,
  type StepProgressProps,
  type StepState,
} from "./composites/step-list.tsx";
export {
  CheckboxList,
  MultiSelect,
  type CheckboxListProps,
  type CheckboxOption,
  type MultiSelectProps,
} from "./composites/multi-select.tsx";
