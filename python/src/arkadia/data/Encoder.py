# encoder.py
"""
Encoder for AK-DATA.

Supports:
- Primitive values
- Record {key:value}
- Lists [ ... ]
- Lists of primitives
- Inline type headers <a:number b:string c:string[]>
"""

import re
from typing import Any, Optional

from .Config import Config
from .Meta import Meta
from .Node import Node
from .Schema import Schema, SchemaKind


class Colors:
    RESET = "\033[0m"
    STRING = "\033[92m"  # green
    NUMBER = "\033[94m"  # blue
    BOOL = "\033[95m"  # magenta
    NULL = "\033[90m"  # gray
    TYPE = "\033[96m"  # cyan
    KEY = "\033[93m"  # yellow
    SCHEMA = "\033[91m"  # red (for @TypeName)
    TAG = "\033[35m"
    ATTR = "\033[93m"


class Encoder:
    def __init__(self, config: Config):
        self.indent = config.get("indent", 2)
        self.start_indent = config.get("start_indent", 0)
        self.compact = config.get("compact", False)
        self.escape_new_lines = config.get("escape_new_lines", False)
        self.colorize = config.get("colorize", False)
        self.include_comments = config.get("include_comments", True)
        self.include_array_size = config.get("include_array_size", False)
        # Lists shorter than this get no $size (with include_array_size).
        self.array_size_min = config.get("array_size_min", 1)
        self.include_schema = config.get("include_schema", True)
        self.include_type = config.get("include_type", True)
        self.include_meta = config.get("include_meta", True)
        # This is special encode, when the schema is icnluded inside sample data
        # [
        # (name: string /name of the user/, age: number /age of the user/),
        # ]
        self.prompt_output = config.get("prompt_output", False)

    # -------------------------------------------------------------
    # PUBLIC ENTRY
    # -------------------------------------------------------------

    def encode(self, node: Node, indent: int = 0, include_schema: bool = True) -> str:
        """
        Encode a Node into ADF text.
        Order: Meta/Comments -> Schema -> Data
        """
        base_indent = self.start_indent + indent

        # 2. Prepare Schema Header (e.g. <test: string>)
        schema_prefix = ""
        should_render_schema = (
            include_schema
            and node.schema is not None
            and self.include_schema  # Config check
        )

        if should_render_schema:
            s_txt = self.encode_schema(node.schema, base_indent).strip()

            if s_txt and not s_txt.startswith("<") and not s_txt.startswith("@"):
                s_txt = f"<{s_txt}>"

            if s_txt:
                if self.compact:
                    schema_prefix = s_txt
                else:
                    # Newline formatting for schema header
                    schema_prefix = s_txt + "\n" + (" " * base_indent)

        # 3. Encode Data
        headerless = (
            node.is_record
            and node.schema is not None
            and not node.schema.fields
            and bool(node.fields)
        )
        if (
            node.is_record
            and node.schema is not None
            and not self.prompt_output
            and (headerless or not self._fits(node, node.schema))
        ):
            # The record's own schema cannot describe it (e.g. an empty key):
            # write it self-describing, without a header.
            return self._named(node)

        if node.is_list:
            data = self._list(node, base_indent, include_schema=False)

        elif node.is_primitive:
            data = self._primitive_node(node)

        elif node.is_record:
            data = self._record(node, base_indent)

        else:
            data = self._c("null", Colors.NULL)

        # Final Assembly: Meta -> Schema -> Data
        return f"{schema_prefix}{data}"

    def encode_schema(
        self, schema: Schema, indent: int = 2, include_meta: bool = True
    ) -> str:
        """
        Encode Schema into AK Data header form.
        Supports: < [ ... ] >, // meta //, $required
        """
        if schema is None:
            return ""

        ind = " " * indent
        prefix = ""

        # Determine padding for brackets based on compact mode
        pad = "" if self.compact else " "

        # Avoid printing internal/default type names
        if schema.type_name and schema.kind == SchemaKind.RECORD and not schema.is_any:
            escaped_name = self._escape_ident(schema.type_name)
            prefix = self._c(f"@{escaped_name}", Colors.SCHEMA)

        meta = self._meta_wrapped(schema) if include_meta else ""

        # --- PRIMITIVE ---
        if schema.is_primitive:
            escaped_type = self._escape_ident(schema.type_name)
            meta_prefix = self._meta_inline(schema) if include_meta else ""
            return (
                ind
                + ((meta_prefix + " ") if meta_prefix else "")
                + self._c(escaped_type, Colors.TYPE)
            )

        # --- LIST ---
        if schema.is_list:
            # Check for Outer Meta for the list itself
            schema.apply_meta(schema.element)
            schema.element.clear_meta()
            list_meta = self._meta_wrapped(schema) if include_meta else ""

            # Special Case: List of Records < [ ... ] >
            if schema.element and schema.element.is_record:
                # We reuse the _record_fields logic but wrap in <[ ... ]>
                inner_fields = self._encode_schema_fields(schema.element)

                # FIX: Use 'pad' variable to remove spaces in compact mode
                return (
                    ind
                    + prefix
                    + "<"
                    + pad
                    + "["
                    + list_meta
                    + inner_fields
                    + pad
                    + "]"
                    + pad
                    + ">"
                )

            # Standard List [Type]
            inner = self.encode_schema(schema.element, 0, False).strip()
            return ind + "[" + list_meta + self._c(inner, Colors.TYPE) + "]"

        # --- RECORD ---
        if schema.is_record:
            # Get Record-level meta (e.g. < / $ver=1 / ... >)
            record_meta = self._meta_wrapped(schema) if include_meta else ""

            if not schema.fields:
                # If the record is generic (no fields, no specific type name, no meta),
                # return an empty string to avoid printing "<>" or "<any>" before the "{...}".
                if not prefix and not record_meta and schema.is_any:
                    return ""
                # FIX: Use 'pad' variable
                return ind + prefix + "<" + pad + record_meta + "any" + pad + ">"

            # Encode Fields
            inner_fields = self._encode_schema_fields(schema)

            # FIX: Use 'pad' variable to remove spaces in compact mode
            # e.g., Compact: <id:int> | Pretty: < id: int >
            return ind + prefix + "<" + pad + record_meta + inner_fields + pad + ">"

        return ind + f"<{meta if include_meta else ''}any>"

    # --- Helper to deduplicate field encoding logic ---
    def _encode_schema_fields(self, schema: Schema) -> str:
        """
        Encodes fields definitions.
        Format: /* comment */ $required $attr=val #tag name: type
        """
        parts = []
        pad = "" if self.compact else " "

        for field in schema.fields:
            field_parts = []

            meta_prefix = self._meta_inline(field)
            if meta_prefix:
                field_parts.append(meta_prefix)

            # 3. Field Name
            escaped_field_name = self._escape_ident(field.name)
            field_parts.append(self._c(escaped_field_name, Colors.KEY))

            # 4. Field Type
            field_type = self.encode_schema(field, 0, False).strip()

            last_idx = len(field_parts) - 1

            # FIX: Logic to decide when to print the type signature.
            # A. If it's a Structure (List/Record), ALWAYS print the type (e.g. [string]),
            #    ignoring the fact that type_name might be default "any".
            # B. If it's a Primitive, print it only if it's not "any" (and types are included).
            # C. Crucial: Ensure field_type is not empty (handles generic empty records).
            is_structure = not field.is_primitive
            is_explicit_primitive = self.include_type and field.type_name != "any"

            if field_type and (is_structure or is_explicit_primitive):
                field_parts[last_idx] += f":{self._c(field_type, Colors.TYPE)}"

            parts.append(" ".join(field_parts))

        sep = f",{pad}"
        return sep.join(parts)

    # -------------------------------------------------------------
    # HELPER: SCHEMA COMPATIBILITY CHECK
    # -------------------------------------------------------------

    def _schemas_are_compatible(
        self, node_schema: Optional[Schema], expected_schema: Optional[Schema]
    ) -> bool:
        """
        Checks if the node's schema matches the parent's expected schema.
        Used to determine if we need to show an inline <type> override.
        """
        if self._open(expected_schema):
            return True

        if node_schema is None:
            return True

        # null decodes as null under any primitive type: no tag needed.
        if (
            node_schema.is_primitive
            and node_schema.type_name == "null"
            and expected_schema.is_primitive
        ):
            return True

        # Check general kind
        if node_schema.kind != expected_schema.kind:
            return False

        # Check specific primitive type name (e.g. int vs string)
        if node_schema.is_primitive and expected_schema.is_primitive:
            # Loose equality: 'number' matches 'int'/'float' usually, but here we check exact name match
            return node_schema.type_name == expected_schema.type_name

        return True

    def _get_type_label(self, schema: Schema) -> str:
        """Generates a short type label for inline overrides <type>."""
        if schema.is_primitive:
            return self._escape_ident(schema.type_name)
        elif schema.is_list:
            inner = self._get_type_label(schema.element)
            return f"[{inner}]"
        elif schema.is_record and schema.type_name and schema.type_name != "any":
            return self._escape_ident(schema.type_name)
        # Fallback for complex inline records
        return "any"

    def _apply_type_tag(
        self,
        val_str: str,
        node_schema: Optional[Schema],
        expected_schema: Optional[Schema],
    ) -> str:
        """
        Applies an inline type tag (e.g., <int>) if the schema does not match the expectation.
        This is the single source of truth for override formatting.
        """
        if self._schemas_are_compatible(node_schema, expected_schema):
            return val_str

        # Mismatch detected -> Wrap with tag
        label = self._get_type_label(node_schema) if node_schema else "any"
        tag = self._c(f"<{label}>", Colors.SCHEMA)
        return f"{tag} {val_str}"

    # -------------------------------------------------------------
    # META AND COMMENTS (Unified Logic)
    # -------------------------------------------------------------

    def _build_meta_string(self, obj: Meta) -> str:
        """
        Internal helper to build the content of metadata string.
        Combines Comments, Attributes, Tags, and Modifiers.
        """
        items = []
        pad = "" if self.compact else " "

        # 1. Comments
        if self.include_comments and obj.comments:
            for c in obj.comments:
                cleaned = c.strip()
                items.append(self._c(f"/*{pad}{cleaned}{pad}*/", Colors.NULL))

        # 2. Modifiers
        if getattr(obj, "required", False):
            items.append(self._c("$required", Colors.TAG))

        # 3. Attributes & Tags
        if self.include_meta:
            current_attr = obj.attr or {}
            for k, v in current_attr.items():
                escaped_key = self._escape_ident(k)
                if isinstance(v, bool) and v is True:
                    items.append(self._c(f"${escaped_key}", Colors.ATTR))
                else:
                    if isinstance(v, (dict, list)):
                        from .api import dumps  # structured value: compact AK-DATA

                        val_str = dumps(v)
                    else:
                        val_str = self._primitive(v)
                    items.append(self._c(f"${escaped_key}=", Colors.ATTR) + val_str)

            current_tags = obj.tags or []
            for t in current_tags:
                items.append(self._c(f"#{t}", Colors.TAG))

        if not items:
            return ""

        content = " ".join(items)

        # Inline: /* c1 */ !req $a=1
        return content

    def _meta_inline(self, obj: Meta) -> str:
        """For Primitives/Fields: No wrappers."""
        return self._build_meta_string(obj)

    def _meta_wrapped(self, obj: Meta) -> str:
        """For Containers/Schema Headers: Wrapped in /.../."""
        content = self._build_meta_string(obj)
        return self._wrap_meta(content)

    def _wrap_meta(self, content: str):
        if not content:
            return ""
        pad = "" if self.compact else " "
        content = (
            self._c(f"//{pad}", Colors.SCHEMA)
            + content
            + self._c(f"{pad}//", Colors.SCHEMA)
        )
        if self.compact:
            return content + " " if content else ""
        else:
            return content if content else ""

    # -------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------
    def _c(self, text: str, color: str) -> str:
        if not self.colorize:
            return text
        return f"{color}{text}{Colors.RESET}"

    def _escape_newlines(self, text: str) -> str:
        return text.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")

    def _primitive_node(self, node: Node) -> str:
        inner_meta = self._meta_inline(node)
        str = self._primitive(node.value)
        return (inner_meta + " " if inner_meta else "") + str

    def _primitive(self, v: Any) -> str:
        if isinstance(v, str):
            return self._string(v)
        if v is True:
            return self._c("true", Colors.BOOL)
        if v is False:
            return self._c("false", Colors.BOOL)
        if v is None:
            return self._c("null", Colors.NULL)
        return self._c(str(v), Colors.NUMBER)

    def _string(self, v: str) -> str:
        # 1. Escape backslashes first! (Critical step)
        content = v.replace("\\", "\\\\")

        # 2. Escape quotes
        content = content.replace('"', '\\"')

        # 3. Handle newlines if needed
        if self.escape_new_lines:
            content = (
                content.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
            )

        return f'"{content}"'

    def _escape_ident(self, name: str) -> str:
        """
        Wraps identifier in backticks if it contains spaces or special characters.
        Regex: [a-zA-Z_][a-zA-Z0-9_]*
        """
        if not name:
            return '""'  # empty key: only valid in named records {"": value}

        # Standard identifier pattern
        pattern = r"^[a-zA-Z_][a-zA-Z0-9_]*$"

        if re.fullmatch(pattern, name):
            return name

        # If it doesn't match, wrap it in backticks
        return f"`{name}`"

    # -------------------------------------------------------------
    # LOSSLESS ENCODING: positional only when the decoder can map it
    # -------------------------------------------------------------
    def _fits(self, node: Node, expected: Optional[Schema]) -> bool:
        """
        True when `node` can be written positionally under `expected`, i.e. the
        decoder will reconstruct exactly the same keys. Records must have the
        same field names (order is taken from `expected`), recursively.
        Primitive type differences are handled with inline <type> tags.
        """
        if self._open(expected):
            return True
        if node.schema is None:
            return True
        if node.is_record:
            if not expected.is_record:
                return False
            names = [f.name for f in expected.fields]
            # Same names as the header, or as its first k fields (the decoder
            # leaves the missing trailing fields out). Field values that differ
            # are tagged one by one in _record.
            k = len(node.fields)
            return (
                1 <= k <= len(names)
                and len(set(names)) == len(names)
                and set(names[:k]) == set(node.fields.keys())
            )
        if node.is_list:
            # Elements that differ are tagged one by one in _list_values.
            return expected.is_list
        return True

    @staticmethod
    def _open(expected: Optional[Schema]) -> bool:
        """True when `expected` puts no structural constraint on a value."""
        if expected is None or expected.kind == SchemaKind.ANY:
            return True
        if expected.is_record:
            return not expected.fields
        return expected.is_primitive and expected.type_name == "any"

    def _record_key(self, key: str) -> str:
        """Key of a named record; a key with a backtick is written quoted."""
        if "`" not in key:
            return self._escape_ident(key)
        body = (
            key.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return f'"{body}"'

    def _named(self, node: Node) -> str:
        """Self-describing form ({key:value}, [..]) that needs no header."""
        sep = "," if self.compact else ", "
        if node.is_record:
            items = []
            for key, child in node.fields.items():
                k = self._c(self._record_key(key), Colors.KEY)
                items.append(
                    f"{k}:{'' if self.compact else ' '}{self._value(child, None)}"
                )
            return "{" + self._meta_wrapped(node) + sep.join(items) + "}"
        if node.is_list:
            return self._value(node, None)
        if node.is_primitive:
            return self._primitive_node(node)
        return self._c("null", Colors.NULL)

    def _value(self, node: Node, expected: Optional[Schema]) -> str:
        """
        Encodes a nested value that the decoder will read with schema `expected`.
        Positional forms are used only when `expected` describes the value;
        otherwise the value describes itself (named record, tagged list).
        """
        is_open = self._open(expected)
        any_tag = self._c("<any>", Colors.SCHEMA) + " "

        if node.is_record:
            if not is_open and self._fits(node, expected):
                return self._record(node, 0, expected)
            named = self._named(node)
            return named if is_open else any_tag + named

        if node.is_list:
            if not is_open and expected.is_list:
                return self._list_values(node, expected.element)
            element = node.schema.element if node.schema else None
            if (
                element is not None
                and not self._open(element)
                and all(self._fits(el, element) for el in node.elements)
                and (element.is_record or not is_open)
                and not (element.is_record and len(node.elements) < 2)
            ):
                # The list carries its own header, e.g. <[id:number,name:string]>.
                tag = self.encode_schema(node.schema, 0, False).strip()
                if not tag.startswith("<"):
                    tag = f"<{tag}>"
                return f"{self._c(tag, Colors.SCHEMA)} " + self._list_values(
                    node, element
                )
            body = self._list_values(node, None)
            return body if is_open else any_tag + body

        val = self.encode(node, 0, include_schema=False).strip()
        return self._apply_type_tag(val, node.schema, expected)

    def _size(self, node: Node) -> None:
        """$size=N on a list (include_array_size, lists of array_size_min+ items)."""
        if self.include_array_size and len(node.elements) >= self.array_size_min:
            node.attr["size"] = len(node.elements)

    def _list_values(self, node: Node, element: Optional[Schema]) -> str:
        """Elements of a nested list, without a header (it is in the parent's)."""
        self._size(node)
        sep = "," if self.compact else ", "
        items = []
        for el in node.elements:
            if el.is_record or el.is_list:
                items.append(self._value(el, element))
            else:
                val = self.encode(el, 0, include_schema=False).strip()
                if not self._schemas_are_compatible(el.schema, element):
                    label = self._get_type_label(el.schema)
                    val = f"{self._c(f'<{label}>', Colors.SCHEMA)} {val}"
                items.append(val)
        return "[" + self._meta_wrapped(node) + sep.join(items) + "]"

    # -------------------------------------------------------------
    # STRUCTURAL LIST: [ Node, Node ]
    # -------------------------------------------------------------
    def _join(self, items: list[str], sep: str) -> str:
        if self.compact:
            return sep.join(items)

        if sep == "\n":
            return sep.join(items)

        # For inline separators (like commas), we add a space for readability
        return f"{sep} ".join(items)

    # -------------------------------------------------------------
    # STRUCTURAL LIST: [ @Schema... (...) (...) ]
    # -------------------------------------------------------------
    def _list(self, node: Node, indent: int, include_schema: bool = False) -> str:
        ind = " " * indent
        child_indent = indent + self.indent
        is_prompt = self.prompt_output

        self._size(node)

        inner_meta = self._meta_wrapped(node)

        # 1. Generate Header Schema (Standard only)
        schema_header = ""
        if not is_prompt and include_schema and node.schema and node.schema.element:
            schema_header = self.encode_schema(node.schema.element, 0).strip()
            if schema_header:
                schema_header += " "

        expected_child = node.schema.element if node.schema else None

        # --- PROMPT MODE (Full Structural Expansion) ---
        if is_prompt:
            res = ind + "[\n"
            if inner_meta:
                res += " " * child_indent + inner_meta + "\n"

            if node.schema and node.schema.element:
                from .Node import Node as DummyNode

                # Force recursion into the element's structure
                dummy = DummyNode(value=None, schema=node.schema.element)

                # We strip() the blueprint because we manually handle the first line's indentation
                blueprint = self.encode(
                    dummy, child_indent, include_schema=False
                ).strip()

                res += " " * child_indent + blueprint + ",\n"
                res += (
                    " " * child_indent
                    + "... /* repeat pattern for additional items */\n"
                )
            else:
                res += " " * child_indent + "/* any content */\n"

            res += ind + "]"
            return res

        # --- COMPACT MODE ---
        if self.compact:
            items = []
            for el in node.elements:
                if el.is_record or el.is_list:
                    items.append(self._value(el, expected_child))
                    continue
                val = self.encode(el, 0, include_schema=False).strip()
                if not self._schemas_are_compatible(el.schema, expected_child):
                    label = self._get_type_label(el.schema)
                    val = f"{self._c(f'<{label}>', Colors.SCHEMA)} {val}"
                items.append(val)
            return ind + "[" + inner_meta + schema_header + ",".join(items) + "]"

        # --- PRETTY MODE ---
        res = ind + "[\n"
        if inner_meta:
            res += " " * child_indent + inner_meta + "\n"
        if schema_header:
            res += " " * child_indent + schema_header.strip() + "\n"

        element_lines = []
        for el in node.elements:
            if el.is_record or el.is_list:
                element_lines.append(
                    " " * child_indent + self._value(el, expected_child)
                )
                continue
            val = self.encode(el, 0, include_schema=False).strip()
            if not self._schemas_are_compatible(el.schema, expected_child):
                label = self._get_type_label(el.schema)
                val = f"{self._c(f'<{label}>', Colors.SCHEMA)} {val}"
            element_lines.append(" " * child_indent + val)

        if element_lines:
            res += ",\n".join(element_lines) + "\n"
        res += ind + "]"
        return res

    # -------------------------------------------------------------
    # RECORD: {key:value} -> (val1, val2) OR {key:value}
    # -------------------------------------------------------------
    def _record(
        self, node: Node, indent: int, expected: Optional[Schema] = None
    ) -> str:
        inner_meta = self._meta_wrapped(node)
        parts = []
        is_prompt = self.prompt_output
        base_ind = " " * indent
        child_ind = " " * (indent + self.indent)
        # Positional order is the order of the schema the decoder will apply.
        layout = (
            expected if expected is not None and expected.is_record else node.schema
        )

        if layout and layout.fields:
            fields = layout.fields
            if not is_prompt:
                # A record that has only the first k fields of the header is
                # written with k values (missing trailing fields stay absent).
                present = [i for i, f in enumerate(fields) if f.name in node.fields]
                if present:
                    fields = fields[: present[-1] + 1]
            for field_def in fields:
                if is_prompt:
                    # --- PROMPT MODE: Type Label or Structural Expansion ---
                    field_name = self._escape_ident(field_def.name)

                    if field_def.is_primitive:
                        # For primitives, we just want the type name (e.g., "number")
                        field_val_structure = self._c(
                            self._get_type_label(field_def), Colors.TYPE
                        )
                    else:
                        # For structures (Records/Lists), we recurse to get the { } or [ ]
                        from .Node import Node as DummyNode

                        dummy_field = DummyNode(value=None, schema=field_def)
                        field_val_structure = self.encode(
                            dummy_field, indent + self.indent, include_schema=False
                        ).strip()

                    line = f"{self._c(field_name, Colors.KEY)}: {field_val_structure}"

                    if field_def.comments:
                        line += f" {self._c(f'/* {field_def.comments[0].strip()} */', Colors.NULL)}"
                    parts.append(line)
                else:
                    # --- STANDARD MODE (Data values) ---
                    field_node = node.fields.get(field_def.name)
                    if field_node:
                        parts.append(self._value(field_node, field_def))
                    else:
                        parts.append(self._c("null", Colors.NULL))
        elif (
            not is_prompt
            and not node.fields
            and not (layout and (layout.comments or layout.attr or layout.tags))
        ):
            # An empty JSON object. (A schema carrying meta keeps the legacy
            # "<// meta // any>(null)" form.)
            return "{" + inner_meta + "}"
        else:
            parts.append(self._c("null", Colors.NULL))

        if is_prompt:
            body = ",\n".join([child_ind + p for p in parts])
            meta_str = child_ind + inner_meta + "\n" if inner_meta else ""
            return "{\n" + meta_str + body + "\n" + base_ind + "}"

        sep = "," if self.compact else ", "
        return "(" + inner_meta + sep.join(parts) + ")"
