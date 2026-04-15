from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field


DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?!-)(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}$"
)
TARGET_TYPE_VALUES = {"ip", "domain", "cidr", "ipv6"}


@dataclass(slots=True)
class ValidationResult:
    is_valid: bool
    normalized_value: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def normalize_target_value(target_type: str, target_value: str) -> str:
    value = (target_value or "").strip()
    if target_type in {"domain", "cidr"}:
        return value.lower()
    return value


def validate_target_syntax(target_type: str, target_value: str) -> ValidationResult:
    target_type = (target_type or "").strip().lower()
    normalized = normalize_target_value(target_type, target_value)

    if target_type not in TARGET_TYPE_VALUES:
        return ValidationResult(
            is_valid=False,
            normalized_value=normalized,
            errors=["Unsupported target type."],
        )

    if not normalized:
        return ValidationResult(
            is_valid=False,
            normalized_value=normalized,
            errors=["Target value is required."],
        )

    try:
        if target_type == "ip":
            ip = ipaddress.IPv4Address(normalized)
            return ValidationResult(is_valid=True, normalized_value=str(ip))
        if target_type == "ipv6":
            ip = ipaddress.IPv6Address(normalized)
            return ValidationResult(is_valid=True, normalized_value=str(ip).lower())
        if target_type == "cidr":
            network = ipaddress.ip_network(normalized, strict=False)
            return ValidationResult(is_valid=True, normalized_value=str(network).lower())
        if target_type == "domain":
            if not DOMAIN_PATTERN.fullmatch(normalized):
                raise ValueError
            return ValidationResult(is_valid=True, normalized_value=normalized.lower())
    except ValueError:
        return ValidationResult(
            is_valid=False,
            normalized_value=normalized,
            errors=[f"Invalid {target_type.upper()} format."],
        )

    return ValidationResult(
        is_valid=False,
        normalized_value=normalized,
        errors=["Unsupported target value."],
    )


def validate_target_policy(target_type: str, normalized_value: str) -> ValidationResult:
    """
    Policy validation is intentionally separated from syntax validation so that
    future allow-list and ownership constraints can be added without touching forms.
    """
    warnings: list[str] = []
    if target_type in {"ip", "ipv6"} and normalized_value in {"0.0.0.0", "::"}:
        warnings.append("Wildcard-style addresses should be reviewed before approval.")
    return ValidationResult(
        is_valid=True,
        normalized_value=normalized_value,
        warnings=warnings,
    )


def validate_target_input(target_type: str, target_value: str) -> ValidationResult:
    syntax_result = validate_target_syntax(target_type, target_value)
    if not syntax_result.is_valid:
        return syntax_result

    policy_result = validate_target_policy(target_type, syntax_result.normalized_value)
    if not policy_result.is_valid:
        return policy_result

    return ValidationResult(
        is_valid=True,
        normalized_value=syntax_result.normalized_value,
        warnings=policy_result.warnings,
    )
