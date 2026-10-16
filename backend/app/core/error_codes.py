"""Error code catalog — GENERATED from spec/kod-uchun/17-api-umumiy.md §15.

Do not edit by hand: run ``uv run python scripts/gen_error_codes.py``.
``http_status`` is None for codes that never appear as an HTTP error
(1C item/task results); 200/202 codes travel in ``warnings[]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class ErrorCode(StrEnum):
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    OTP_INVALID = "OTP_INVALID"
    OTP_EXPIRED = "OTP_EXPIRED"
    OTP_MAX_ATTEMPTS = "OTP_MAX_ATTEMPTS"
    OTP_CHANNEL_UNAVAILABLE = "OTP_CHANNEL_UNAVAILABLE"
    TELEGRAM_NOT_LINKED = "TELEGRAM_NOT_LINKED"
    GOOGLE_EMAIL_NOT_VERIFIED = "GOOGLE_EMAIL_NOT_VERIFIED"
    GOOGLE_AUTH_FAILED = "GOOGLE_AUTH_FAILED"
    CSRF_INVALID = "CSRF_INVALID"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    DEVICE_REVOKED = "DEVICE_REVOKED"
    PIN_INVALID = "PIN_INVALID"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    NOT_FOUND = "NOT_FOUND"
    DOC_NOT_DRAFT = "DOC_NOT_DRAFT"
    DOC_ALREADY_CANCELLED = "DOC_ALREADY_CANCELLED"
    DOC_INVALID_STATE = "DOC_INVALID_STATE"
    RESOURCE_ARCHIVED = "RESOURCE_ARCHIVED"
    SYSTEM_ROLE_READONLY = "SYSTEM_ROLE_READONLY"
    BARCODE_DUPLICATE = "BARCODE_DUPLICATE"
    CATEGORY_HAS_PRODUCTS = "CATEGORY_HAS_PRODUCTS"
    MXIK_CODE_INVALID = "MXIK_CODE_INVALID"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    BRANCH_SCOPE_DENIED = "BRANCH_SCOPE_DENIED"
    OWNER_ONLY = "OWNER_ONLY"
    PLATFORM_ADMIN_REQUIRED = "PLATFORM_ADMIN_REQUIRED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_INVALID = "APPROVAL_INVALID"
    APPROVAL_REQUEST_ALREADY_RESOLVED = "APPROVAL_REQUEST_ALREADY_RESOLVED"
    APPROVAL_REQUEST_EXPIRED = "APPROVAL_REQUEST_EXPIRED"
    DISCOUNT_LIMIT_EXCEEDED = "DISCOUNT_LIMIT_EXCEEDED"
    RETURN_LIMIT_EXCEEDED = "RETURN_LIMIT_EXCEEDED"
    CASH_WITHDRAW_LIMIT_EXCEEDED = "CASH_WITHDRAW_LIMIT_EXCEEDED"
    DEBT_LIMIT_EXCEEDED = "DEBT_LIMIT_EXCEEDED"
    PRICE_CHANGE_LIMIT_EXCEEDED = "PRICE_CHANGE_LIMIT_EXCEEDED"
    WRITE_OFF_LIMIT_EXCEEDED = "WRITE_OFF_LIMIT_EXCEEDED"
    EXPENSE_LIMIT_EXCEEDED = "EXPENSE_LIMIT_EXCEEDED"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    RETURN_QTY_EXCEEDED = "RETURN_QTY_EXCEEDED"
    NEGATIVE_STOCK_NOT_ALLOWED = "NEGATIVE_STOCK_NOT_ALLOWED"
    LOT_NOT_FOUND = "LOT_NOT_FOUND"
    STOCK_NEGATIVE = "STOCK_NEGATIVE"
    LOT_ALREADY_CONSUMED = "LOT_ALREADY_CONSUMED"
    BARCODE_NOT_IN_CATALOG = "BARCODE_NOT_IN_CATALOG"
    VALUATION_METHOD_CHANGE_NOT_ALLOWED = "VALUATION_METHOD_CHANGE_NOT_ALLOWED"
    WAREHOUSE_ACCOUNT_LOCKED = "WAREHOUSE_ACCOUNT_LOCKED"
    COUNT_LINES_INCOMPLETE = "COUNT_LINES_INCOMPLETE"
    SHIFT_NOT_OPEN = "SHIFT_NOT_OPEN"
    SHIFT_ALREADY_OPEN = "SHIFT_ALREADY_OPEN"
    DEBT_ALREADY_PAID = "DEBT_ALREADY_PAID"
    DOUBTFUL_FLAG_REQUIRES_OWNER = "DOUBTFUL_FLAG_REQUIRES_OWNER"
    RECEIPT_SEQ_CONFLICT = "RECEIPT_SEQ_CONFLICT"
    SHIFT_DEVICE_MISMATCH = "SHIFT_DEVICE_MISMATCH"
    FISCAL_SEND_FAILED = "FISCAL_SEND_FAILED"
    FISCAL_OFFLINE_48H_BLOCKED = "FISCAL_OFFLINE_48H_BLOCKED"
    FISCAL_DEVICE_LOCKED = "FISCAL_DEVICE_LOCKED"
    MARKING_CODE_INVALID = "MARKING_CODE_INVALID"
    MARKING_CODE_ALREADY_SOLD = "MARKING_CODE_ALREADY_SOLD"
    MARKING_PRICE_UNKNOWN_OFFLINE = "MARKING_PRICE_UNKNOWN_OFFLINE"
    MARKING_VERIFY_FAILED = "MARKING_VERIFY_FAILED"
    MARKING_VERIFY_UNAVAILABLE = "MARKING_VERIFY_UNAVAILABLE"
    MARKING_PRECHECK_WARNING = "MARKING_PRECHECK_WARNING"
    MARKING_RETURN_REQUIRES_ONLINE = "MARKING_RETURN_REQUIRES_ONLINE"
    CARD_TERMINAL_UNREACHABLE = "CARD_TERMINAL_UNREACHABLE"
    CARD_TERMINAL_BUSY = "CARD_TERMINAL_BUSY"
    CARD_TERMINAL_TIMEOUT = "CARD_TERMINAL_TIMEOUT"
    CARD_DECLINED = "CARD_DECLINED"
    CARD_OUTCOME_UNKNOWN = "CARD_OUTCOME_UNKNOWN"
    CARD_AMOUNT_MISMATCH = "CARD_AMOUNT_MISMATCH"
    CARD_MANUAL_NOT_ALLOWED = "CARD_MANUAL_NOT_ALLOWED"
    CARD_MANUAL_APPROVAL_REQUIRED = "CARD_MANUAL_APPROVAL_REQUIRED"
    CARD_VOID_FAILED = "CARD_VOID_FAILED"
    CARD_TRANSACTION_MISMATCH = "CARD_TRANSACTION_MISMATCH"
    EIMZO_SIGN_FAILED = "EIMZO_SIGN_FAILED"
    EINVOICE_ALREADY_LINKED = "EINVOICE_ALREADY_LINKED"
    EINVOICE_AMOUNT_EXCEEDS_RECEIPT = "EINVOICE_AMOUNT_EXCEEDS_RECEIPT"
    EINVOICE_COUNTERPARTY_INCOMPLETE = "EINVOICE_COUNTERPARTY_INCOMPLETE"
    EINVOICE_NOT_ACCEPTED = "EINVOICE_NOT_ACCEPTED"
    EINVOICE_NOT_SIGNED = "EINVOICE_NOT_SIGNED"
    EINVOICE_ALREADY_SIGNED = "EINVOICE_ALREADY_SIGNED"
    EINVOICE_PROVIDER_UNAVAILABLE = "EINVOICE_PROVIDER_UNAVAILABLE"
    ETTN_REQUIRED = "ETTN_REQUIRED"
    ETTN_CANCEL_IN_OPERATOR = "ETTN_CANCEL_IN_OPERATOR"
    PAYMENT_PROVIDER_ERROR = "PAYMENT_PROVIDER_ERROR"
    PAYMENT_NOT_CONFIRMED = "PAYMENT_NOT_CONFIRMED"
    PURCHASE_ORDER_CLOSED = "PURCHASE_ORDER_CLOSED"
    SUPPLIER_OVERPAY_BLOCKED = "SUPPLIER_OVERPAY_BLOCKED"
    SUPPLIER_OVERPAY_ADVANCE = "SUPPLIER_OVERPAY_ADVANCE"
    IMPORT_FILE_INVALID = "IMPORT_FILE_INVALID"
    IMPORT_JOB_NOT_VALIDATED = "IMPORT_JOB_NOT_VALIDATED"
    IMPORT_JOB_ALREADY_COMMITTED = "IMPORT_JOB_ALREADY_COMMITTED"
    BANK_IMPORT_FILE_INVALID = "BANK_IMPORT_FILE_INVALID"
    BANK_IMPORT_ACCOUNT_MISMATCH = "BANK_IMPORT_ACCOUNT_MISMATCH"
    BANK_IMPORT_DUPLICATE = "BANK_IMPORT_DUPLICATE"
    SUBSCRIPTION_RESTRICTED = "SUBSCRIPTION_RESTRICTED"
    SUBSCRIPTION_PAYMENT_FAILED = "SUBSCRIPTION_PAYMENT_FAILED"
    ADDON_REQUIRED = "ADDON_REQUIRED"
    SALE_NOT_FOUND = "SALE_NOT_FOUND"
    SYNC_SCOPE_DENIED = "SYNC_SCOPE_DENIED"
    DEPENDENCY_NOT_SYNCED = "DEPENDENCY_NOT_SYNCED"
    IDEMPOTENCY_IN_PROGRESS = "IDEMPOTENCY_IN_PROGRESS"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    PERIOD_CLOSED = "PERIOD_CLOSED"
    RECOST_REJECTED_PERIOD_CLOSED = "RECOST_REJECTED_PERIOD_CLOSED"
    PERIOD_ALREADY_CLOSED = "PERIOD_ALREADY_CLOSED"
    PERIOD_CLOSE_NOT_READY = "PERIOD_CLOSE_NOT_READY"
    PERIOD_CLOSE_OUT_OF_ORDER = "PERIOD_CLOSE_OUT_OF_ORDER"
    AI_LIMIT_EXCEEDED = "AI_LIMIT_EXCEEDED"
    AI_PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"
    AI_LOW_CONFIDENCE = "AI_LOW_CONFIDENCE"
    OCR_IMAGE_UNREADABLE = "OCR_IMAGE_UNREADABLE"
    AI_CONSENT_REQUIRED = "AI_CONSENT_REQUIRED"
    AI_FEATURE_DISABLED = "AI_FEATURE_DISABLED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    EXPORT_JOB_FAILED = "EXPORT_JOB_FAILED"
    WEBHOOK_SIGNATURE_INVALID = "WEBHOOK_SIGNATURE_INVALID"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOTIFY_CONSENT_REQUIRED = "NOTIFY_CONSENT_REQUIRED"
    AGENT_CAPABILITY_DISABLED = "AGENT_CAPABILITY_DISABLED"
    ONEC_AGENT_OFFLINE = "ONEC_AGENT_OFFLINE"
    ONEC_AGENT_REVOKED = "ONEC_AGENT_REVOKED"
    ONEC_AGENT_UPDATE_REQUIRED = "ONEC_AGENT_UPDATE_REQUIRED"
    ONEC_PAIRING_CODE_INVALID = "ONEC_PAIRING_CODE_INVALID"
    ONEC_PAIRING_CODE_EXPIRED = "ONEC_PAIRING_CODE_EXPIRED"
    ONEC_BASE_DUPLICATE = "ONEC_BASE_DUPLICATE"
    ONEC_BASE_NOT_READY = "ONEC_BASE_NOT_READY"
    ONEC_BASE_NOT_ON_PC = "ONEC_BASE_NOT_ON_PC"
    ONEC_WRITE_DISABLED = "ONEC_WRITE_DISABLED"
    ONEC_PC_WRITE_DISABLED = "ONEC_PC_WRITE_DISABLED"
    ONEC_PROFILE_UNSUPPORTED = "ONEC_PROFILE_UNSUPPORTED"
    ONEC_CLOUD_BASE_UNSUPPORTED = "ONEC_CLOUD_BASE_UNSUPPORTED"
    ONEC_EDITION_NO_COM = "ONEC_EDITION_NO_COM"
    ONEC_SALE_PRICE_ACCOUNTING_UNSUPPORTED = "ONEC_SALE_PRICE_ACCOUNTING_UNSUPPORTED"
    ONEC_TAX_REGIME_MISMATCH = "ONEC_TAX_REGIME_MISMATCH"
    ONEC_ORGANIZATION_NOT_FOUND = "ONEC_ORGANIZATION_NOT_FOUND"
    ONEC_METADATA_MISMATCH = "ONEC_METADATA_MISMATCH"
    ONEC_MARKING_CHECK_ENABLED = "ONEC_MARKING_CHECK_ENABLED"
    ONEC_USER_TOO_PRIVILEGED = "ONEC_USER_TOO_PRIVILEGED"
    ONEC_LICENSE_SEPARATE_REQUIRED = "ONEC_LICENSE_SEPARATE_REQUIRED"
    ONEC_NEGATIVE_STOCK_ALLOWED = "ONEC_NEGATIVE_STOCK_ALLOWED"
    ONEC_SETTING_NOT_SUPPORTED = "ONEC_SETTING_NOT_SUPPORTED"
    ONEC_BEFORE_START_DATE = "ONEC_BEFORE_START_DATE"
    ONEC_NOTHING_TO_EXPORT = "ONEC_NOTHING_TO_EXPORT"
    ONEC_BATCH_INVALID_STATE = "ONEC_BATCH_INVALID_STATE"
    ONEC_ACTIVE_BATCH_EXISTS = "ONEC_ACTIVE_BATCH_EXISTS"
    ONEC_PREVIEW_CHANGED = "ONEC_PREVIEW_CHANGED"
    ONEC_WARNINGS_NOT_ACKNOWLEDGED = "ONEC_WARNINGS_NOT_ACKNOWLEDGED"
    ONEC_MAPPING_INCOMPLETE = "ONEC_MAPPING_INCOMPLETE"
    ONEC_MAPPING_IN_USE = "ONEC_MAPPING_IN_USE"
    ONEC_CATALOG_CACHE_EMPTY = "ONEC_CATALOG_CACHE_EMPTY"
    ONEC_ALREADY_MAPPED = "ONEC_ALREADY_MAPPED"
    ONEC_REF_TYPE_MISMATCH = "ONEC_REF_TYPE_MISMATCH"
    ONEC_REF_CREATE_FORBIDDEN = "ONEC_REF_CREATE_FORBIDDEN"
    ONEC_PAYMENT_ACCOUNT_NOT_TRANSIT = "ONEC_PAYMENT_ACCOUNT_NOT_TRANSIT"
    ONEC_SHIFTS_OPEN = "ONEC_SHIFTS_OPEN"
    ONEC_DEVICES_NOT_SYNCED = "ONEC_DEVICES_NOT_SYNCED"
    ONEC_PREVIOUS_DAY_NOT_DONE = "ONEC_PREVIOUS_DAY_NOT_DONE"
    ONEC_QUEUED_BEHIND = "ONEC_QUEUED_BEHIND"
    ONEC_DATE_PROHIBITED = "ONEC_DATE_PROHIBITED"
    ONEC_Z_REPORT_DIFF = "ONEC_Z_REPORT_DIFF"
    ONEC_STOCK_SHORTAGE = "ONEC_STOCK_SHORTAGE"
    ONEC_TRANSFER_CROSS_BASE = "ONEC_TRANSFER_CROSS_BASE"
    ONEC_LATE_DATA = "ONEC_LATE_DATA"
    ONEC_UNPOST_REQUIRED = "ONEC_UNPOST_REQUIRED"
    ONEC_ORP_CASH_MISMATCH = "ONEC_ORP_CASH_MISMATCH"
    ONEC_BUILD_INVARIANT_FAILED = "ONEC_BUILD_INVARIANT_FAILED"
    ONEC_TOTALS_MISMATCH = "ONEC_TOTALS_MISMATCH"
    ONEC_TASK_LEASE_LOST = "ONEC_TASK_LEASE_LOST"
    ONEC_TASK_REJECTED = "ONEC_TASK_REJECTED"
    ONEC_COM_NOT_REGISTERED = "ONEC_COM_NOT_REGISTERED"
    ONEC_BITNESS_MISMATCH = "ONEC_BITNESS_MISMATCH"
    ONEC_PLATFORM_VERSION_MISMATCH = "ONEC_PLATFORM_VERSION_MISMATCH"
    ONEC_AUTH_FAILED = "ONEC_AUTH_FAILED"
    ONEC_BASE_UNAVAILABLE = "ONEC_BASE_UNAVAILABLE"
    ONEC_BASE_LOCKED = "ONEC_BASE_LOCKED"
    ONEC_BASE_EXCLUSIVE = "ONEC_BASE_EXCLUSIVE"
    ONEC_LICENSE_UNAVAILABLE = "ONEC_LICENSE_UNAVAILABLE"
    ONEC_LOCK_CONFLICT = "ONEC_LOCK_CONFLICT"
    ONEC_OBJECT_LOCKED = "ONEC_OBJECT_LOCKED"
    ONEC_ACCESS_DENIED = "ONEC_ACCESS_DENIED"
    ONEC_NO_RIGHTS = "ONEC_NO_RIGHTS"
    ONEC_NEGATIVE_STOCK = "ONEC_NEGATIVE_STOCK"
    ONEC_FILL_CHECK_FAILED = "ONEC_FILL_CHECK_FAILED"
    ONEC_POST_FAILED = "ONEC_POST_FAILED"
    ONEC_WRITE_FAILED = "ONEC_WRITE_FAILED"
    ONEC_REF_NOT_FOUND = "ONEC_REF_NOT_FOUND"
    ONEC_REF_MARKED_FOR_DELETION = "ONEC_REF_MARKED_FOR_DELETION"
    ONEC_REF_AMBIGUOUS = "ONEC_REF_AMBIGUOUS"
    ONEC_FIELD_VERIFY_FAILED = "ONEC_FIELD_VERIFY_FAILED"
    ONEC_OBJECT_MARKED_DELETED = "ONEC_OBJECT_MARKED_DELETED"
    ONEC_EXISTS_DIFFERENT = "ONEC_EXISTS_DIFFERENT"
    ONEC_DUPLICATE_REF = "ONEC_DUPLICATE_REF"
    ONEC_CHANGED_IN_1C = "ONEC_CHANGED_IN_1C"
    ONEC_QUERY_FAILED = "ONEC_QUERY_FAILED"
    ONEC_CONNECTION_LOST = "ONEC_CONNECTION_LOST"
    ONEC_TIMEOUT = "ONEC_TIMEOUT"
    ONEC_WORKER_CRASHED = "ONEC_WORKER_CRASHED"
    ONEC_UNKNOWN_OUTCOME = "ONEC_UNKNOWN_OUTCOME"
    ONEC_DPAPI_FAILED = "ONEC_DPAPI_FAILED"
    ONEC_UNKNOWN = "ONEC_UNKNOWN"


@dataclass(frozen=True, slots=True)
class ErrorSpec:
    domain: str
    http_status: int | None
    message_key: str


ERROR_SPECS: Final[dict[ErrorCode, ErrorSpec]] = {
    ErrorCode.UNAUTHORIZED: ErrorSpec("Autentifikatsiya", 401, "errors.unauthorized"),
    ErrorCode.INVALID_CREDENTIALS: ErrorSpec("Autentifikatsiya", 401, "errors.invalid_credentials"),
    ErrorCode.ACCOUNT_LOCKED: ErrorSpec("Autentifikatsiya", 423, "errors.account_locked"),
    ErrorCode.OTP_INVALID: ErrorSpec("Autentifikatsiya", 400, "errors.otp_invalid"),
    ErrorCode.OTP_EXPIRED: ErrorSpec("Autentifikatsiya", 400, "errors.otp_expired"),
    ErrorCode.OTP_MAX_ATTEMPTS: ErrorSpec("Autentifikatsiya", 429, "errors.otp_max_attempts"),
    ErrorCode.OTP_CHANNEL_UNAVAILABLE: ErrorSpec("Autentifikatsiya", 503, "errors.otp_channel_unavailable"),
    ErrorCode.TELEGRAM_NOT_LINKED: ErrorSpec("Autentifikatsiya", 200, "errors.telegram_not_linked"),
    ErrorCode.GOOGLE_EMAIL_NOT_VERIFIED: ErrorSpec("Autentifikatsiya", 403, "errors.google_email_not_verified"),
    ErrorCode.GOOGLE_AUTH_FAILED: ErrorSpec("Autentifikatsiya", 401, "errors.google_auth_failed"),
    ErrorCode.CSRF_INVALID: ErrorSpec("Autentifikatsiya", 403, "errors.csrf_invalid"),
    ErrorCode.TOKEN_EXPIRED: ErrorSpec("Autentifikatsiya", 401, "errors.token_expired"),
    ErrorCode.TOKEN_REVOKED: ErrorSpec("Autentifikatsiya", 401, "errors.token_revoked"),
    ErrorCode.DEVICE_REVOKED: ErrorSpec("Autentifikatsiya", 403, "errors.device_revoked"),
    ErrorCode.PIN_INVALID: ErrorSpec("Autentifikatsiya", 400, "errors.pin_invalid"),
    ErrorCode.VALIDATION_ERROR: ErrorSpec("Validatsiya", 422, "errors.validation"),
    ErrorCode.VERSION_CONFLICT: ErrorSpec("Validatsiya", 409, "errors.version_conflict"),
    ErrorCode.NOT_FOUND: ErrorSpec("Validatsiya", 404, "errors.not_found"),
    ErrorCode.DOC_NOT_DRAFT: ErrorSpec("Validatsiya", 409, "errors.doc_not_draft"),
    ErrorCode.DOC_ALREADY_CANCELLED: ErrorSpec("Validatsiya", 409, "errors.doc_already_cancelled"),
    ErrorCode.DOC_INVALID_STATE: ErrorSpec("Validatsiya", 409, "errors.doc_invalid_state"),
    ErrorCode.RESOURCE_ARCHIVED: ErrorSpec("Validatsiya", 409, "errors.resource_archived"),
    ErrorCode.SYSTEM_ROLE_READONLY: ErrorSpec("Validatsiya", 409, "errors.system_role_readonly"),
    ErrorCode.BARCODE_DUPLICATE: ErrorSpec("Validatsiya", 409, "errors.barcode_duplicate"),
    ErrorCode.CATEGORY_HAS_PRODUCTS: ErrorSpec("Validatsiya", 409, "errors.category_has_products"),
    ErrorCode.MXIK_CODE_INVALID: ErrorSpec("Validatsiya", 422, "errors.mxik_code_invalid"),
    ErrorCode.PERMISSION_DENIED: ErrorSpec("Ruxsat", 403, "errors.permission_denied"),
    ErrorCode.BRANCH_SCOPE_DENIED: ErrorSpec("Ruxsat", 403, "errors.branch_scope_denied"),
    ErrorCode.OWNER_ONLY: ErrorSpec("Ruxsat", 403, "errors.owner_only"),
    ErrorCode.PLATFORM_ADMIN_REQUIRED: ErrorSpec("Ruxsat", 403, "errors.platform_admin_required"),
    ErrorCode.APPROVAL_REQUIRED: ErrorSpec("Ruxsat", 202, "errors.approval_required"),
    ErrorCode.APPROVAL_INVALID: ErrorSpec("Ruxsat", 403, "errors.approval_invalid"),
    ErrorCode.APPROVAL_REQUEST_ALREADY_RESOLVED: ErrorSpec("Ruxsat", 409, "errors.approval_request_already_resolved"),
    ErrorCode.APPROVAL_REQUEST_EXPIRED: ErrorSpec("Ruxsat", 409, "errors.approval_request_expired"),
    ErrorCode.DISCOUNT_LIMIT_EXCEEDED: ErrorSpec("Limitlar", 403, "errors.discount_limit_exceeded"),
    ErrorCode.RETURN_LIMIT_EXCEEDED: ErrorSpec("Limitlar", 403, "errors.return_limit_exceeded"),
    ErrorCode.CASH_WITHDRAW_LIMIT_EXCEEDED: ErrorSpec("Limitlar", 403, "errors.cash_withdraw_limit_exceeded"),
    ErrorCode.DEBT_LIMIT_EXCEEDED: ErrorSpec("Limitlar", 403, "errors.debt_limit_exceeded"),
    ErrorCode.PRICE_CHANGE_LIMIT_EXCEEDED: ErrorSpec("Limitlar", 403, "errors.price_change_limit_exceeded"),
    ErrorCode.WRITE_OFF_LIMIT_EXCEEDED: ErrorSpec("Limitlar", 403, "errors.write_off_limit_exceeded"),
    ErrorCode.EXPENSE_LIMIT_EXCEEDED: ErrorSpec("Limitlar", 403, "errors.expense_limit_exceeded"),
    ErrorCode.INSUFFICIENT_STOCK: ErrorSpec("Ombor/qoldiq", 422, "errors.insufficient_stock"),
    ErrorCode.RETURN_QTY_EXCEEDED: ErrorSpec("Ombor/qoldiq", 422, "errors.return_qty_exceeded"),
    ErrorCode.NEGATIVE_STOCK_NOT_ALLOWED: ErrorSpec("Ombor/qoldiq", 422, "errors.negative_stock_not_allowed"),
    ErrorCode.LOT_NOT_FOUND: ErrorSpec("Ombor/qoldiq", 404, "errors.lot_not_found"),
    ErrorCode.STOCK_NEGATIVE: ErrorSpec("Ombor/qoldiq", 200, "warnings.stock_negative"),
    ErrorCode.LOT_ALREADY_CONSUMED: ErrorSpec("Ombor/qoldiq", 409, "errors.lot_already_consumed"),
    ErrorCode.BARCODE_NOT_IN_CATALOG: ErrorSpec("Ombor/qoldiq", 422, "errors.barcode_not_in_catalog"),
    ErrorCode.VALUATION_METHOD_CHANGE_NOT_ALLOWED: ErrorSpec("Ombor/qoldiq", 409, "errors.valuation_method_change_not_allowed"),
    ErrorCode.WAREHOUSE_ACCOUNT_LOCKED: ErrorSpec("Ombor/qoldiq", 409, "errors.warehouse_account_locked"),
    ErrorCode.COUNT_LINES_INCOMPLETE: ErrorSpec("Ombor/qoldiq", 422, "errors.count_lines_incomplete"),
    ErrorCode.SHIFT_NOT_OPEN: ErrorSpec("Kassa/smena", 409, "errors.shift_not_open"),
    ErrorCode.SHIFT_ALREADY_OPEN: ErrorSpec("Kassa/smena", 409, "errors.shift_already_open"),
    ErrorCode.DEBT_ALREADY_PAID: ErrorSpec("Qarz", 409, "errors.debt_already_paid"),
    ErrorCode.DOUBTFUL_FLAG_REQUIRES_OWNER: ErrorSpec("Qarz", 403, "errors.doubtful_flag_requires_owner"),
    ErrorCode.RECEIPT_SEQ_CONFLICT: ErrorSpec("Fiskal/markirovka", 409, "errors.receipt_seq_conflict"),
    ErrorCode.SHIFT_DEVICE_MISMATCH: ErrorSpec("Fiskal/markirovka", 409, "errors.shift_device_mismatch"),
    ErrorCode.FISCAL_SEND_FAILED: ErrorSpec("Fiskal/markirovka", 502, "errors.fiscal_send_failed"),
    ErrorCode.FISCAL_OFFLINE_48H_BLOCKED: ErrorSpec("Fiskal/markirovka", 409, "errors.fiscal_offline_48h_blocked"),
    ErrorCode.FISCAL_DEVICE_LOCKED: ErrorSpec("Fiskal/markirovka", 409, "errors.fiscal_device_locked"),
    ErrorCode.MARKING_CODE_INVALID: ErrorSpec("Fiskal/markirovka", 422, "errors.marking_code_invalid"),
    ErrorCode.MARKING_CODE_ALREADY_SOLD: ErrorSpec("Fiskal/markirovka", 409, "errors.marking_code_already_sold"),
    ErrorCode.MARKING_PRICE_UNKNOWN_OFFLINE: ErrorSpec("Fiskal/markirovka", 422, "errors.marking_price_unknown_offline"),
    ErrorCode.MARKING_VERIFY_FAILED: ErrorSpec("Fiskal/markirovka", 409, "errors.marking_verify_failed"),
    ErrorCode.MARKING_VERIFY_UNAVAILABLE: ErrorSpec("Fiskal/markirovka", 503, "errors.marking_verify_unavailable"),
    ErrorCode.MARKING_PRECHECK_WARNING: ErrorSpec("Fiskal/markirovka", 200, "warnings.marking_precheck"),
    ErrorCode.MARKING_RETURN_REQUIRES_ONLINE: ErrorSpec("Fiskal/markirovka", 422, "errors.marking_return_requires_online"),
    ErrorCode.CARD_TERMINAL_UNREACHABLE: ErrorSpec("Karta terminali", 503, "errors.card_terminal_unreachable"),
    ErrorCode.CARD_TERMINAL_BUSY: ErrorSpec("Karta terminali", 409, "errors.card_terminal_busy"),
    ErrorCode.CARD_TERMINAL_TIMEOUT: ErrorSpec("Karta terminali", 504, "errors.card_terminal_timeout"),
    ErrorCode.CARD_DECLINED: ErrorSpec("Karta terminali", 200, "errors.card_declined"),
    ErrorCode.CARD_OUTCOME_UNKNOWN: ErrorSpec("Karta terminali", 409, "errors.card_outcome_unknown"),
    ErrorCode.CARD_AMOUNT_MISMATCH: ErrorSpec("Karta terminali", 422, "errors.card_amount_mismatch"),
    ErrorCode.CARD_MANUAL_NOT_ALLOWED: ErrorSpec("Karta terminali", 403, "errors.card_manual_not_allowed"),
    ErrorCode.CARD_MANUAL_APPROVAL_REQUIRED: ErrorSpec("Karta terminali", 403, "errors.card_manual_approval_required"),
    ErrorCode.CARD_VOID_FAILED: ErrorSpec("Karta terminali", 502, "errors.card_void_failed"),
    ErrorCode.CARD_TRANSACTION_MISMATCH: ErrorSpec("Karta terminali", 409, "errors.card_transaction_mismatch"),
    ErrorCode.EIMZO_SIGN_FAILED: ErrorSpec("E-faktura", 422, "errors.eimzo_sign_failed"),
    ErrorCode.EINVOICE_ALREADY_LINKED: ErrorSpec("E-faktura", 409, "errors.einvoice_already_linked"),
    ErrorCode.EINVOICE_AMOUNT_EXCEEDS_RECEIPT: ErrorSpec("E-faktura", 422, "errors.einvoice_amount_exceeds_receipt"),
    ErrorCode.EINVOICE_COUNTERPARTY_INCOMPLETE: ErrorSpec("E-faktura", 422, "errors.einvoice_counterparty_incomplete"),
    ErrorCode.EINVOICE_NOT_ACCEPTED: ErrorSpec("E-faktura", 409, "errors.einvoice_not_accepted"),
    ErrorCode.EINVOICE_NOT_SIGNED: ErrorSpec("E-faktura", 409, "errors.einvoice_not_signed"),
    ErrorCode.EINVOICE_ALREADY_SIGNED: ErrorSpec("E-faktura", 409, "errors.einvoice_already_signed"),
    ErrorCode.EINVOICE_PROVIDER_UNAVAILABLE: ErrorSpec("E-faktura", 503, "errors.einvoice_provider_unavailable"),
    ErrorCode.ETTN_REQUIRED: ErrorSpec("E-faktura", 409, "errors.ettn_required"),
    ErrorCode.ETTN_CANCEL_IN_OPERATOR: ErrorSpec("E-faktura", 200, "warnings.ettn_cancel_in_operator"),
    ErrorCode.PAYMENT_PROVIDER_ERROR: ErrorSpec("To'lov/xarid", 502, "errors.payment_provider_error"),
    ErrorCode.PAYMENT_NOT_CONFIRMED: ErrorSpec("To'lov/xarid", 422, "errors.payment_not_confirmed"),
    ErrorCode.PURCHASE_ORDER_CLOSED: ErrorSpec("To'lov/xarid", 409, "errors.purchase_order_closed"),
    ErrorCode.SUPPLIER_OVERPAY_BLOCKED: ErrorSpec("To'lov/xarid", 422, "errors.supplier_overpay_blocked"),
    ErrorCode.SUPPLIER_OVERPAY_ADVANCE: ErrorSpec("To'lov/xarid", 200, "warnings.supplier_overpay_advance"),
    ErrorCode.IMPORT_FILE_INVALID: ErrorSpec("Import", 422, "errors.import_file_invalid"),
    ErrorCode.IMPORT_JOB_NOT_VALIDATED: ErrorSpec("Import", 409, "errors.import_job_not_validated"),
    ErrorCode.IMPORT_JOB_ALREADY_COMMITTED: ErrorSpec("Import", 409, "errors.import_job_already_committed"),
    ErrorCode.BANK_IMPORT_FILE_INVALID: ErrorSpec("Bank ko'chirmasi", 422, "errors.bank_import_file_invalid"),
    ErrorCode.BANK_IMPORT_ACCOUNT_MISMATCH: ErrorSpec("Bank ko'chirmasi", 422, "errors.bank_import_account_mismatch"),
    ErrorCode.BANK_IMPORT_DUPLICATE: ErrorSpec("Bank ko'chirmasi", 409, "errors.bank_import_duplicate"),
    ErrorCode.SUBSCRIPTION_RESTRICTED: ErrorSpec("Obuna/platforma", 403, "errors.subscription_restricted"),
    ErrorCode.SUBSCRIPTION_PAYMENT_FAILED: ErrorSpec("Obuna/platforma", 422, "errors.subscription_payment_failed"),
    ErrorCode.ADDON_REQUIRED: ErrorSpec("Obuna/platforma", 403, "errors.addon_required"),
    ErrorCode.SALE_NOT_FOUND: ErrorSpec("Sinxronizatsiya", 422, "errors.sale_not_found"),
    ErrorCode.SYNC_SCOPE_DENIED: ErrorSpec("Sinxronizatsiya", 403, "errors.sync_scope_denied"),
    ErrorCode.DEPENDENCY_NOT_SYNCED: ErrorSpec("Sinxronizatsiya", 422, "errors.dependency_not_synced"),
    ErrorCode.IDEMPOTENCY_IN_PROGRESS: ErrorSpec("Idempotentlik", 409, "errors.idempotency_in_progress"),
    ErrorCode.IDEMPOTENCY_KEY_REUSED: ErrorSpec("Idempotentlik", 422, "errors.idempotency_key_reused"),
    ErrorCode.PERIOD_CLOSED: ErrorSpec("Davr/buxgalteriya", 409, "errors.period_closed"),
    ErrorCode.RECOST_REJECTED_PERIOD_CLOSED: ErrorSpec("Davr/buxgalteriya", 409, "errors.recost_rejected_period_closed"),
    ErrorCode.PERIOD_ALREADY_CLOSED: ErrorSpec("Davr/buxgalteriya", 409, "errors.period_already_closed"),
    ErrorCode.PERIOD_CLOSE_NOT_READY: ErrorSpec("Davr/buxgalteriya", 409, "errors.period_close_not_ready"),
    ErrorCode.PERIOD_CLOSE_OUT_OF_ORDER: ErrorSpec("Davr/buxgalteriya", 409, "errors.period_close_out_of_order"),
    ErrorCode.AI_LIMIT_EXCEEDED: ErrorSpec("AI", 429, "errors.ai_limit_exceeded"),
    ErrorCode.AI_PROVIDER_UNAVAILABLE: ErrorSpec("AI", 503, "errors.ai_provider_unavailable"),
    ErrorCode.AI_LOW_CONFIDENCE: ErrorSpec("AI", 200, "errors.ai_low_confidence"),
    ErrorCode.OCR_IMAGE_UNREADABLE: ErrorSpec("AI", 200, "errors.ocr_image_unreadable"),
    ErrorCode.AI_CONSENT_REQUIRED: ErrorSpec("AI", 403, "errors.ai_consent_required"),
    ErrorCode.AI_FEATURE_DISABLED: ErrorSpec("AI", 403, "errors.ai_feature_disabled"),
    ErrorCode.FILE_TOO_LARGE: ErrorSpec("Fayl/umumiy", 413, "errors.file_too_large"),
    ErrorCode.UNSUPPORTED_FILE_TYPE: ErrorSpec("Fayl/umumiy", 415, "errors.unsupported_file_type"),
    ErrorCode.EXPORT_JOB_FAILED: ErrorSpec("Fayl/umumiy", 200, "errors.export_job_failed"),
    ErrorCode.WEBHOOK_SIGNATURE_INVALID: ErrorSpec("Fayl/umumiy", 403, "errors.webhook_signature_invalid"),
    ErrorCode.RATE_LIMITED: ErrorSpec("Fayl/umumiy", 429, "errors.rate_limited"),
    ErrorCode.INTERNAL_ERROR: ErrorSpec("Fayl/umumiy", 500, "errors.internal_error"),
    ErrorCode.NOTIFY_CONSENT_REQUIRED: ErrorSpec("Fayl/umumiy", 422, "errors.notify_consent_required"),
    ErrorCode.AGENT_CAPABILITY_DISABLED: ErrorSpec("Do'kon agenti", 409, "errors.agent_capability_disabled"),
    ErrorCode.ONEC_AGENT_OFFLINE: ErrorSpec("1C integratsiyasi", 202, "warnings.onec.agent_offline"),
    ErrorCode.ONEC_AGENT_REVOKED: ErrorSpec("1C integratsiyasi", 403, "errors.onec.agent_revoked"),
    ErrorCode.ONEC_AGENT_UPDATE_REQUIRED: ErrorSpec("1C integratsiyasi", 426, "errors.onec.agent_update_required"),
    ErrorCode.ONEC_PAIRING_CODE_INVALID: ErrorSpec("1C integratsiyasi", 404, "errors.onec.pairing_code_invalid"),
    ErrorCode.ONEC_PAIRING_CODE_EXPIRED: ErrorSpec("1C integratsiyasi", 409, "errors.onec.pairing_code_expired"),
    ErrorCode.ONEC_BASE_DUPLICATE: ErrorSpec("1C integratsiyasi", 409, "errors.onec.base_duplicate"),
    ErrorCode.ONEC_BASE_NOT_READY: ErrorSpec("1C integratsiyasi", 409, "errors.onec.base_not_ready"),
    ErrorCode.ONEC_BASE_NOT_ON_PC: ErrorSpec("1C integratsiyasi", None, "errors.onec.base_not_on_pc"),
    ErrorCode.ONEC_WRITE_DISABLED: ErrorSpec("1C integratsiyasi", 409, "errors.onec.write_disabled"),
    ErrorCode.ONEC_PC_WRITE_DISABLED: ErrorSpec("1C integratsiyasi", None, "errors.onec.pc_write_disabled"),
    ErrorCode.ONEC_PROFILE_UNSUPPORTED: ErrorSpec("1C integratsiyasi", 422, "errors.onec.profile_unsupported"),
    ErrorCode.ONEC_CLOUD_BASE_UNSUPPORTED: ErrorSpec("1C integratsiyasi", 422, "errors.onec.cloud_base_unsupported"),
    ErrorCode.ONEC_EDITION_NO_COM: ErrorSpec("1C integratsiyasi", None, "errors.onec.edition_no_com"),
    ErrorCode.ONEC_SALE_PRICE_ACCOUNTING_UNSUPPORTED: ErrorSpec("1C integratsiyasi", None, "errors.onec.sale_price_accounting_unsupported"),
    ErrorCode.ONEC_TAX_REGIME_MISMATCH: ErrorSpec("1C integratsiyasi", None, "errors.onec.tax_regime_mismatch"),
    ErrorCode.ONEC_ORGANIZATION_NOT_FOUND: ErrorSpec("1C integratsiyasi", None, "errors.onec.organization_not_found"),
    ErrorCode.ONEC_METADATA_MISMATCH: ErrorSpec("1C integratsiyasi", None, "errors.onec.metadata_mismatch"),
    ErrorCode.ONEC_MARKING_CHECK_ENABLED: ErrorSpec("1C integratsiyasi", None, "warnings.onec.marking_check_enabled"),
    ErrorCode.ONEC_USER_TOO_PRIVILEGED: ErrorSpec("1C integratsiyasi", None, "warnings.onec.user_too_privileged"),
    ErrorCode.ONEC_LICENSE_SEPARATE_REQUIRED: ErrorSpec("1C integratsiyasi", None, "warnings.onec.license_separate_required"),
    ErrorCode.ONEC_NEGATIVE_STOCK_ALLOWED: ErrorSpec("1C integratsiyasi", None, "warnings.onec.negative_stock_allowed"),
    ErrorCode.ONEC_SETTING_NOT_SUPPORTED: ErrorSpec("1C integratsiyasi", 422, "errors.onec.setting_not_supported"),
    ErrorCode.ONEC_BEFORE_START_DATE: ErrorSpec("1C integratsiyasi", 422, "errors.onec.before_start_date"),
    ErrorCode.ONEC_NOTHING_TO_EXPORT: ErrorSpec("1C integratsiyasi", 422, "errors.onec.nothing_to_export"),
    ErrorCode.ONEC_BATCH_INVALID_STATE: ErrorSpec("1C integratsiyasi", 409, "errors.onec.batch_invalid_state"),
    ErrorCode.ONEC_ACTIVE_BATCH_EXISTS: ErrorSpec("1C integratsiyasi", 409, "errors.onec.active_batch_exists"),
    ErrorCode.ONEC_PREVIEW_CHANGED: ErrorSpec("1C integratsiyasi", 409, "errors.onec.preview_changed"),
    ErrorCode.ONEC_WARNINGS_NOT_ACKNOWLEDGED: ErrorSpec("1C integratsiyasi", 422, "errors.onec.warnings_not_acknowledged"),
    ErrorCode.ONEC_MAPPING_INCOMPLETE: ErrorSpec("1C integratsiyasi", 409, "errors.onec.mapping_incomplete"),
    ErrorCode.ONEC_MAPPING_IN_USE: ErrorSpec("1C integratsiyasi", 409, "errors.onec.mapping_in_use"),
    ErrorCode.ONEC_CATALOG_CACHE_EMPTY: ErrorSpec("1C integratsiyasi", 409, "errors.onec.catalog_cache_empty"),
    ErrorCode.ONEC_ALREADY_MAPPED: ErrorSpec("1C integratsiyasi", 409, "errors.onec.already_mapped"),
    ErrorCode.ONEC_REF_TYPE_MISMATCH: ErrorSpec("1C integratsiyasi", 422, "errors.onec.ref_type_mismatch"),
    ErrorCode.ONEC_REF_CREATE_FORBIDDEN: ErrorSpec("1C integratsiyasi", 403, "errors.onec.ref_create_forbidden"),
    ErrorCode.ONEC_PAYMENT_ACCOUNT_NOT_TRANSIT: ErrorSpec("1C integratsiyasi", None, "warnings.onec.payment_account_not_transit"),
    ErrorCode.ONEC_SHIFTS_OPEN: ErrorSpec("1C integratsiyasi", 409, "errors.onec.shifts_open"),
    ErrorCode.ONEC_DEVICES_NOT_SYNCED: ErrorSpec("1C integratsiyasi", 409, "errors.onec.devices_not_synced"),
    ErrorCode.ONEC_PREVIOUS_DAY_NOT_DONE: ErrorSpec("1C integratsiyasi", 409, "errors.onec.previous_day_not_done"),
    ErrorCode.ONEC_QUEUED_BEHIND: ErrorSpec("1C integratsiyasi", None, "warnings.onec.queued_behind"),
    ErrorCode.ONEC_DATE_PROHIBITED: ErrorSpec("1C integratsiyasi", 409, "errors.onec.date_prohibited"),
    ErrorCode.ONEC_Z_REPORT_DIFF: ErrorSpec("1C integratsiyasi", None, "warnings.onec.z_report_diff"),
    ErrorCode.ONEC_STOCK_SHORTAGE: ErrorSpec("1C integratsiyasi", None, "warnings.onec.stock_shortage"),
    ErrorCode.ONEC_TRANSFER_CROSS_BASE: ErrorSpec("1C integratsiyasi", None, "warnings.onec.transfer_cross_base"),
    ErrorCode.ONEC_LATE_DATA: ErrorSpec("1C integratsiyasi", None, "warnings.onec.late_data"),
    ErrorCode.ONEC_UNPOST_REQUIRED: ErrorSpec("1C integratsiyasi", None, "warnings.onec.unpost_required"),
    ErrorCode.ONEC_ORP_CASH_MISMATCH: ErrorSpec("1C integratsiyasi", None, "errors.onec.orp_cash_mismatch"),
    ErrorCode.ONEC_BUILD_INVARIANT_FAILED: ErrorSpec("1C integratsiyasi", None, "errors.onec.build_invariant_failed"),
    ErrorCode.ONEC_TOTALS_MISMATCH: ErrorSpec("1C integratsiyasi", None, "errors.onec.totals_mismatch"),
    ErrorCode.ONEC_TASK_LEASE_LOST: ErrorSpec("1C integratsiyasi", 409, "errors.onec.task_lease_lost"),
    ErrorCode.ONEC_TASK_REJECTED: ErrorSpec("1C integratsiyasi", None, "errors.onec.task_rejected"),
    ErrorCode.ONEC_COM_NOT_REGISTERED: ErrorSpec("1C integratsiyasi", None, "errors.onec.com_not_registered"),
    ErrorCode.ONEC_BITNESS_MISMATCH: ErrorSpec("1C integratsiyasi", None, "errors.onec.bitness_mismatch"),
    ErrorCode.ONEC_PLATFORM_VERSION_MISMATCH: ErrorSpec("1C integratsiyasi", None, "errors.onec.platform_version_mismatch"),
    ErrorCode.ONEC_AUTH_FAILED: ErrorSpec("1C integratsiyasi", None, "errors.onec.auth_failed"),
    ErrorCode.ONEC_BASE_UNAVAILABLE: ErrorSpec("1C integratsiyasi", None, "errors.onec.base_unavailable"),
    ErrorCode.ONEC_BASE_LOCKED: ErrorSpec("1C integratsiyasi", None, "errors.onec.base_locked"),
    ErrorCode.ONEC_BASE_EXCLUSIVE: ErrorSpec("1C integratsiyasi", None, "errors.onec.base_exclusive"),
    ErrorCode.ONEC_LICENSE_UNAVAILABLE: ErrorSpec("1C integratsiyasi", None, "errors.onec.license_unavailable"),
    ErrorCode.ONEC_LOCK_CONFLICT: ErrorSpec("1C integratsiyasi", None, "errors.onec.lock_conflict"),
    ErrorCode.ONEC_OBJECT_LOCKED: ErrorSpec("1C integratsiyasi", None, "errors.onec.object_locked"),
    ErrorCode.ONEC_ACCESS_DENIED: ErrorSpec("1C integratsiyasi", None, "errors.onec.access_denied"),
    ErrorCode.ONEC_NO_RIGHTS: ErrorSpec("1C integratsiyasi", None, "errors.onec.no_rights"),
    ErrorCode.ONEC_NEGATIVE_STOCK: ErrorSpec("1C integratsiyasi", None, "errors.onec.negative_stock"),
    ErrorCode.ONEC_FILL_CHECK_FAILED: ErrorSpec("1C integratsiyasi", None, "errors.onec.fill_check_failed"),
    ErrorCode.ONEC_POST_FAILED: ErrorSpec("1C integratsiyasi", None, "errors.onec.post_failed"),
    ErrorCode.ONEC_WRITE_FAILED: ErrorSpec("1C integratsiyasi", None, "errors.onec.write_failed"),
    ErrorCode.ONEC_REF_NOT_FOUND: ErrorSpec("1C integratsiyasi", None, "errors.onec.ref_not_found"),
    ErrorCode.ONEC_REF_MARKED_FOR_DELETION: ErrorSpec("1C integratsiyasi", None, "errors.onec.ref_marked_for_deletion"),
    ErrorCode.ONEC_REF_AMBIGUOUS: ErrorSpec("1C integratsiyasi", None, "errors.onec.ref_ambiguous"),
    ErrorCode.ONEC_FIELD_VERIFY_FAILED: ErrorSpec("1C integratsiyasi", None, "errors.onec.field_verify_failed"),
    ErrorCode.ONEC_OBJECT_MARKED_DELETED: ErrorSpec("1C integratsiyasi", None, "errors.onec.object_marked_deleted"),
    ErrorCode.ONEC_EXISTS_DIFFERENT: ErrorSpec("1C integratsiyasi", None, "errors.onec.exists_different"),
    ErrorCode.ONEC_DUPLICATE_REF: ErrorSpec("1C integratsiyasi", None, "errors.onec.duplicate_ref"),
    ErrorCode.ONEC_CHANGED_IN_1C: ErrorSpec("1C integratsiyasi", None, "errors.onec.changed_in_1c"),
    ErrorCode.ONEC_QUERY_FAILED: ErrorSpec("1C integratsiyasi", None, "errors.onec.query_failed"),
    ErrorCode.ONEC_CONNECTION_LOST: ErrorSpec("1C integratsiyasi", None, "errors.onec.connection_lost"),
    ErrorCode.ONEC_TIMEOUT: ErrorSpec("1C integratsiyasi", None, "errors.onec.timeout"),
    ErrorCode.ONEC_WORKER_CRASHED: ErrorSpec("1C integratsiyasi", None, "errors.onec.worker_crashed"),
    ErrorCode.ONEC_UNKNOWN_OUTCOME: ErrorSpec("1C integratsiyasi", None, "errors.onec.unknown_outcome"),
    ErrorCode.ONEC_DPAPI_FAILED: ErrorSpec("1C integratsiyasi", None, "errors.onec.dpapi_failed"),
    ErrorCode.ONEC_UNKNOWN: ErrorSpec("1C integratsiyasi", None, "errors.onec.unknown"),
}
