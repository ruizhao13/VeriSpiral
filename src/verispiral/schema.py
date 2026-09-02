"""A deliberately small JSON-Schema subset used by the public demo.

The project avoids runtime dependencies, so this module implements only the
keywords used by the schemas shipped in this repository.  It is not intended
to replace a complete JSON-Schema implementation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, order=True)
class ValidationIssue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def load_schema(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"schema root must be an object: {path}")
    return value


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValueError(f"unsupported schema type: {expected}")


def validate(instance: Any, schema: Mapping[str, Any], path: str = "$") -> list[ValidationIssue]:
    """Return every validation issue found for the supported schema subset."""

    issues: list[ValidationIssue] = []
    expected = schema.get("type")
    if expected is not None:
        expected_types = [expected] if isinstance(expected, str) else list(expected)
        if not any(_matches_type(instance, item) for item in expected_types):
            label = " or ".join(expected_types)
            return [ValidationIssue(path, f"expected {label}")]

    if "enum" in schema and instance not in schema["enum"]:
        issues.append(ValidationIssue(path, f"must be one of {schema['enum']}"))
    if "const" in schema and instance != schema["const"]:
        issues.append(ValidationIssue(path, f"must equal {schema['const']!r}"))

    if isinstance(instance, Mapping):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                issues.append(ValidationIssue(path, f"missing required property {key!r}"))

        property_names = schema.get("propertyNames")
        if isinstance(property_names, Mapping):
            for key in instance:
                issues.extend(
                    validate(key, property_names, f"{path}.{key!r}<property-name>")
                )

        properties = schema.get("properties", {})
        for key, value in instance.items():
            child_path = f"{path}.{key}"
            if key in properties:
                issues.extend(validate(value, properties[key], child_path))
            elif schema.get("additionalProperties") is False:
                issues.append(ValidationIssue(child_path, "unexpected property"))
            elif isinstance(schema.get("additionalProperties"), Mapping):
                issues.extend(
                    validate(value, schema["additionalProperties"], child_path)
                )

        minimum = schema.get("minProperties")
        if minimum is not None and len(instance) < minimum:
            issues.append(ValidationIssue(path, f"needs at least {minimum} properties"))

    if isinstance(instance, list):
        minimum = schema.get("minItems")
        if minimum is not None and len(instance) < minimum:
            issues.append(ValidationIssue(path, f"needs at least {minimum} items"))
        maximum = schema.get("maxItems")
        if maximum is not None and len(instance) > maximum:
            issues.append(ValidationIssue(path, f"allows at most {maximum} items"))
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in instance]
            if len(encoded) != len(set(encoded)):
                issues.append(ValidationIssue(path, "items must be unique"))
        item_schema = schema.get("items")
        if item_schema:
            for index, value in enumerate(instance):
                issues.extend(validate(value, item_schema, f"{path}[{index}]"))

    if isinstance(instance, str):
        minimum = schema.get("minLength")
        if minimum is not None and len(instance) < minimum:
            issues.append(ValidationIssue(path, f"needs at least {minimum} characters"))
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, instance) is None:
            issues.append(ValidationIssue(path, f"does not match pattern {pattern!r}"))

    return sorted(issues)
