# Changelog

All notable changes to this project will be documented in this file.

## [0.1.11] - 2027-02-20

### Added
- **Escaped Identifiers**: Support for backticks (`` ` ``) in identifiers. Names containing spaces or special characters (e.g., `@`User ID+``, `` `is - special?` ``) are now valid.
- **Smart Encoding**: The encoder now automatically wraps identifiers in backticks only when they do not match the standard `[a-zA-Z_][a-zA-Z0-9_]*` regex.
- **Boolean Flag Support**: Metadata attributes with `true` values are now rendered as clean flags (e.g., `$required` instead of `$required=true`).

### Changed
- **List Formatting (Pretty Mode)**: 
    - Moved `$size` attribute into the standard metadata block (`// $size=N //`).
    - Fixed missing commas between list elements in non-compact mode.
    - Improved indentation logic for multiline lists.
- **Metadata Standardization**: Transitioned validation logic from `!required` suffix to `$required` metadata attribute to maintain the Passive Data Principle.

### Removed
- **`!required` Modifier**: Removed functional support for the `!` suffix in schema definitions to prevent lexical conflicts with future updates. It remains as a syntax-highlighting-only token.

### Fixed
- Fixed a bug in `Encoder.ts` and `Encoder.py` where metadata lines in lists were incorrectly suffixed with commas.
- Corrected identifier parsing logic to strictly terminate at the first closing backtick (no internal escaping).