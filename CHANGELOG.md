# Changelog

All notable changes to this project will be documented in this file.


## [0.1.11] - 2026-02-20

### Added
* **Prompt Output Mode**: Introduced `prompt_output` configuration. When enabled, the encoder generates a "Structural Blueprint" instead of raw data.
* Records expand into `{ key: type /* comment */ }` blocks.
* Lists render a single representative element followed by a continuation hint (`...`).
* Recursive expansion of nested anonymous schemas (no more `any` labels).
* **LLM Hinting**: Automatic injection of field comments into the prompt output to improve AI generation accuracy.
* **Escaped Identifiers**: Support for backticks (```) in identifiers. Names containing spaces or special characters (e.g., `@`User ID+`, ` `is - special?` ``) are now valid.
* **Smart Encoding**: The encoder now automatically wraps identifiers in backticks only when they do not match the standard `[a-zA-Z_][a-zA-Z0-9_]*` regex.
* **Boolean Flag Support**: Metadata attributes with `true` values are now rendered as clean flags (e.g., `$required` instead of `$required=true`).

### Changed

* **List Formatting (Pretty Mode)**:
* Moved `$size` attribute into the standard metadata block (`// $size=N //`).
* Fixed missing commas between list elements in non-compact mode.
* Improved indentation logic for multiline lists.


* **Metadata Standardization**: Transitioned validation logic from `!required` suffix to `$required` metadata attribute to maintain the Passive Data Principle.

### Removed

* **`!required` Modifier**: Removed functional support for the `!` suffix in schema definitions. It remains as a syntax-highlighting-only token.

### Fixed

* Fixed a bug in `Encoder.ts` and `Encoder.py` where metadata lines in lists were incorrectly suffixed with commas.
* Corrected identifier parsing logic to strictly terminate at the first closing backtick (no internal escaping).
