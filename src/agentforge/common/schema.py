from __future__ import annotations

import re
from typing import Any


Schema = dict[str, Any] | bool | None


def validate_json_schema(schema: Schema, value: Any, label: str = "value") -> list[str]:
    """Validate a practical JSON Schema subset without external dependencies."""
    if schema is None or schema is True or schema == {}:
        return []
    if schema is False:
        return [f"{label} is not allowed."]
    if not isinstance(schema, dict):
        return []

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        return [f"{label} must be {_type_label(expected_type)}."]

    errors: list[str] = []
    errors.extend(_validate_const_and_enum(schema, value, label))
    errors.extend(_validate_combinators(schema, value, label))

    if isinstance(value, dict):
        errors.extend(_validate_object(schema, value, label))
    elif _has_object_keywords(schema):
        required = schema.get("required")
        if isinstance(required, list) and required:
            errors.append(f"{label} must be an object with required fields: {', '.join(map(str, required))}.")

    if isinstance(value, list):
        errors.extend(_validate_array(schema, value, label))

    if isinstance(value, str):
        errors.extend(_validate_string(schema, value, label))

    if _is_number(value):
        errors.extend(_validate_number(schema, value, label))

    return errors


def _validate_const_and_enum(schema: dict[str, Any], value: Any, label: str) -> list[str]:
    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{label} must equal {schema['const']!r}.")
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        errors.append(f"{label} must be one of: {', '.join(repr(item) for item in enum_values)}.")
    return errors


def _validate_combinators(schema: dict[str, Any], value: Any, label: str) -> list[str]:
    errors: list[str] = []

    all_of = [item for item in schema.get("allOf", []) if isinstance(item, (dict, bool))]
    for branch in all_of:
        errors.extend(validate_json_schema(branch, value, label))

    any_of = [item for item in schema.get("anyOf", []) if isinstance(item, (dict, bool))]
    if any_of:
        branch_errors = [validate_json_schema(branch, value, label) for branch in any_of]
        if all(branch_error for branch_error in branch_errors):
            details = " | ".join("; ".join(branch_error) for branch_error in branch_errors[:3])
            errors.append(f"{label} must match at least one supported schema: {details}.")

    one_of = [item for item in schema.get("oneOf", []) if isinstance(item, (dict, bool))]
    if one_of:
        branch_errors = [validate_json_schema(branch, value, label) for branch in one_of]
        matches = sum(1 for branch_error in branch_errors if not branch_error)
        if matches != 1:
            errors.append(f"{label} must match exactly one supported schema.")

    not_schema = schema.get("not")
    if isinstance(not_schema, (dict, bool)) and not validate_json_schema(not_schema, value, label):
        errors.append(f"{label} must not match the disallowed schema.")

    return errors


def _validate_object(schema: dict[str, Any], value: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []

    required = schema.get("required")
    if isinstance(required, list):
        for key in required:
            if isinstance(key, str) and key not in value:
                errors.append(f"{label}.{key} is required.")

    properties = schema.get("properties")
    known_properties = set(properties) if isinstance(properties, dict) else set()
    if isinstance(properties, dict):
        for key, field_schema in properties.items():
            if key in value:
                errors.extend(validate_json_schema(field_schema, value[key], f"{label}.{key}"))

    matched_pattern_keys: set[str] = set()
    pattern_properties = schema.get("patternProperties")
    if isinstance(pattern_properties, dict):
        for pattern, field_schema in pattern_properties.items():
            if not isinstance(pattern, str):
                continue
            regex = _compile_pattern(pattern)
            if regex is None:
                continue
            for key, item in value.items():
                if regex.search(key):
                    matched_pattern_keys.add(key)
                    errors.extend(validate_json_schema(field_schema, item, f"{label}.{key}"))

    additional = schema.get("additionalProperties", True)
    for key in sorted(set(value) - known_properties - matched_pattern_keys):
        if additional is False:
            errors.append(f"{label}.{key} is not allowed.")
        elif isinstance(additional, (dict, bool)):
            errors.extend(validate_json_schema(additional, value[key], f"{label}.{key}"))

    min_properties = schema.get("minProperties")
    if isinstance(min_properties, int) and len(value) < min_properties:
        errors.append(f"{label} must have at least {min_properties} properties.")
    max_properties = schema.get("maxProperties")
    if isinstance(max_properties, int) and len(value) > max_properties:
        errors.append(f"{label} must have at most {max_properties} properties.")

    property_names = schema.get("propertyNames")
    if isinstance(property_names, (dict, bool)):
        for key in sorted(value):
            errors.extend(validate_json_schema(property_names, key, f"{label}.{key}"))

    dependent_required = schema.get("dependentRequired")
    if isinstance(dependent_required, dict):
        for key, dependencies in dependent_required.items():
            if key not in value or not isinstance(dependencies, list):
                continue
            for dependency in dependencies:
                if isinstance(dependency, str) and dependency not in value:
                    errors.append(f"{label}.{dependency} is required when {label}.{key} is present.")

    return errors


def _validate_array(schema: dict[str, Any], value: list[Any], label: str) -> list[str]:
    errors: list[str] = []

    min_items = schema.get("minItems")
    if isinstance(min_items, int) and len(value) < min_items:
        errors.append(f"{label} must contain at least {min_items} items.")
    max_items = schema.get("maxItems")
    if isinstance(max_items, int) and len(value) > max_items:
        errors.append(f"{label} must contain at most {max_items} items.")

    if schema.get("uniqueItems") is True:
        seen: list[Any] = []
        for item in value:
            if item in seen:
                errors.append(f"{label} must contain unique items.")
                break
            seen.append(item)

    items = schema.get("items")
    if isinstance(items, (dict, bool)):
        for index, item in enumerate(value):
            errors.extend(validate_json_schema(items, item, f"{label}[{index}]"))
    elif isinstance(items, list):
        for index, item_schema in enumerate(items):
            if index < len(value):
                errors.extend(validate_json_schema(item_schema, value[index], f"{label}[{index}]"))
        additional_items = schema.get("additionalItems", True)
        if len(value) > len(items):
            for index in range(len(items), len(value)):
                if additional_items is False:
                    errors.append(f"{label}[{index}] is not allowed.")
                elif isinstance(additional_items, (dict, bool)):
                    errors.extend(validate_json_schema(additional_items, value[index], f"{label}[{index}]"))

    contains = schema.get("contains")
    if isinstance(contains, (dict, bool)) and not any(not validate_json_schema(contains, item, label) for item in value):
        errors.append(f"{label} must contain an item matching the expected schema.")

    return errors


def _validate_string(schema: dict[str, Any], value: str, label: str) -> list[str]:
    errors: list[str] = []

    min_length = schema.get("minLength")
    if isinstance(min_length, int) and len(value) < min_length:
        errors.append(f"{label} must be at least {min_length} characters.")
    max_length = schema.get("maxLength")
    if isinstance(max_length, int) and len(value) > max_length:
        errors.append(f"{label} must be at most {max_length} characters.")

    pattern = schema.get("pattern")
    if isinstance(pattern, str):
        regex = _compile_pattern(pattern)
        if regex is not None and not regex.search(value):
            errors.append(f"{label} must match pattern {pattern!r}.")

    return errors


def _validate_number(schema: dict[str, Any], value: int | float, label: str) -> list[str]:
    errors: list[str] = []

    minimum = schema.get("minimum")
    if _is_number(minimum) and value < minimum:
        errors.append(f"{label} must be greater than or equal to {minimum}.")
    maximum = schema.get("maximum")
    if _is_number(maximum) and value > maximum:
        errors.append(f"{label} must be less than or equal to {maximum}.")
    exclusive_minimum = schema.get("exclusiveMinimum")
    if _is_number(exclusive_minimum) and value <= exclusive_minimum:
        errors.append(f"{label} must be greater than {exclusive_minimum}.")
    exclusive_maximum = schema.get("exclusiveMaximum")
    if _is_number(exclusive_maximum) and value >= exclusive_maximum:
        errors.append(f"{label} must be less than {exclusive_maximum}.")
    multiple_of = schema.get("multipleOf")
    if _is_number(multiple_of) and multiple_of != 0 and value % multiple_of != 0:
        errors.append(f"{label} must be a multiple of {multiple_of}.")

    return errors


def _matches_type(value: Any, expected_type: Any) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_type(value, item) for item in expected_type)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return _is_number(value)
    if expected_type == "null":
        return value is None
    return True


def _type_label(expected_type: Any) -> str:
    if isinstance(expected_type, list):
        return " or ".join(str(item) for item in expected_type)
    return str(expected_type)


def _has_object_keywords(schema: dict[str, Any]) -> bool:
    return any(key in schema for key in ("required", "properties", "additionalProperties", "patternProperties"))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _compile_pattern(pattern: str) -> re.Pattern[str] | None:
    try:
        return re.compile(pattern)
    except re.error:
        return None
