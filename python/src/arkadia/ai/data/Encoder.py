# encoder.py
"""
Encoder for AI.DATA-FORMAT.

Supports:
- Primitive values
- Record {key:value}
- Lists [ ... ]
- Lists of primitives
- Inline type headers <a:number b:string c:string[]>
"""

from email import header
from typing import Any, Optional, Union
from xml.etree.ElementTree import indent
from .Node import Node
from .Schema import Schema, SchemaKind
from .Meta import Meta
from .Config import Config


class Colors:
    RESET = "\033[0m"
    STRING = "\033[92m"  # green
    NUMBER = "\033[94m"  # blue
    BOOL = "\033[95m"  # magenta
    NULL = "\033[90m"  # gray
    TYPE = "\033[96m"  # cyan
    KEY = "\033[93m"  # yellow
    SCHEMA = "\033[91m"  # red (for @TypeName)
    TAG = "\033[91m"
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
            and self.include_schema # Config check
        )
        
        if should_render_schema:
            s_txt = self.encode_schema(node.schema, base_indent).strip()

            if  not s_txt.startswith("<") and not s_txt.startswith("@"): 
                s_txt = f"<{s_txt}>"

            if s_txt:
                if self.compact:
                    schema_prefix = s_txt
                else:
                    # Newline formatting for schema header
                    schema_prefix = s_txt + "\n" + (" " * base_indent)
                    
        # 3. Encode Data
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



    def encode_schema(self, schema: Schema, indent: int = 2, include_meta: bool = True) -> str:
        """
        Encode Schema into AI.Data header form.
        Supports: < [ ... ] >, / meta /, !required
        """
        if schema is None:
            return ""

        ind = " " * indent
        prefix = ""
        
        # Determine padding for brackets based on compact mode
        pad = "" if self.compact else " "

        # Avoid printing internal/default type names
        if (
            schema.type_name
            and schema.kind == SchemaKind.RECORD
            and not schema.is_any
        ):
            prefix = self._c(f"@{schema.type_name}", Colors.SCHEMA)

        meta = self._meta_wrapped(schema) if include_meta else ""

        # --- PRIMITIVE ---
        if schema.is_primitive:
            meta_prefix = self._meta_inline(schema) if include_meta else ""
            return ind + ((meta_prefix + " ") if meta_prefix else "") + self._c(schema.type_name, Colors.TYPE)

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
                return ind + prefix + "<" + pad + "[" + list_meta + inner_fields + pad + "]" + pad + ">"

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
        Format: /* comment */ !required $attr=val #tag name: type
        """
        parts = []
        pad = "" if self.compact else " "

        for field in schema.fields:
            field_parts = []

            meta_prefix = self._meta_inline(field)
            if meta_prefix:
                field_parts.append(meta_prefix)

            # 3. Field Name
            field_parts.append(self._c(field.name, Colors.KEY))

            # 4. Field Type
            field_type = self.encode_schema(field, 0, False).strip()
            
            last_idx = len(field_parts) - 1
            
            # FIX: Logic to decide when to print the type signature.
            # A. If it's a Structure (List/Record), ALWAYS print the type (e.g. [string]), 
            #    ignoring the fact that type_name might be default "any".
            # B. If it's a Primitive, print it only if it's not "any" (and types are included).
            # C. Crucial: Ensure field_type is not empty (handles generic empty records).
            is_structure = not field.is_primitive
            is_explicit_primitive = (self.include_type and field.type_name != "any")
            
            if field_type and (is_structure or is_explicit_primitive):
                field_parts[last_idx] += f":{self._c(field_type, Colors.TYPE)}"
            
            parts.append(" ".join(field_parts))

        sep = f",{pad}"
        return sep.join(parts)


    # -------------------------------------------------------------
    # HELPER: SCHEMA COMPATIBILITY CHECK
    # -------------------------------------------------------------
    
    def _schemas_are_compatible(self, node_schema: Optional[Schema], expected_schema: Optional[Schema]) -> bool:
        """
        Checks if the node's schema matches the parent's expected schema.
        Used to determine if we need to show an inline <type> override.
        """
        if not expected_schema or expected_schema.is_any:
            return True
        
        if node_schema is None:
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
            return schema.type_name
        elif schema.is_list:
            inner = self._get_type_label(schema.element)
            return f"[{inner}]"
        elif schema.is_record and schema.type_name and schema.type_name != "any":
            return schema.type_name
        # Fallback for complex inline records
        return "any"

    def _apply_type_tag(self, val_str: str, node_schema: Optional[Schema], expected_schema: Optional[Schema]) -> str:
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
        pad =  ""  if self.compact else " "

        # 1. Comments
        if self.include_comments and obj.comments:
            for c in obj.comments:
                cleaned = c.strip()
                items.append(self._c(f"/*{pad}{cleaned}{pad}*/", Colors.NULL))

        # 2. Modifiers
        if getattr(obj, 'required', False):
            items.append(self._c("!required", Colors.TAG))

        # 3. Attributes & Tags
        if self.include_meta:
            current_attr = obj.attr or {}
            for k, v in current_attr.items():
                val_str = self._primitive(v)
                items.append(self._c(f"${k}=", Colors.ATTR) + val_str)

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
        pad =  ""  if self.compact else " "
        content = self._c(f"/{pad}", Colors.SCHEMA) + content + self._c(f"{pad}/", Colors.SCHEMA)
        if self.compact:
            return content + " " if content else ""
        else:
            return " " + content + " " if content else ""
   
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
        content = v
        if self.escape_new_lines:
            content = self._escape_newlines(content)
        content = content.replace('"', '\\"')
        return self._c(f'"{content}"', Colors.STRING)

    # -------------------------------------------------------------
    # PRIMITIVE LIST: ["a","b","c"]
    # -------------------------------------------------------------

    def _list_header(self, node: Node) -> str:
        header = "["
        if self.include_array_size:
            # Prefer elemeents length if available
            size = (
                len(node.elements)
            )
            header += f"{self._c('$size', Colors.KEY)}={self._c(str(size), Colors.NUMBER)}{self._c(':', Colors.TYPE)}"
        return header

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

        inner_meta = self._meta_wrapped(node)

        # 1. Generate Header Schema (if requested)
        schema_header = ""
        if include_schema and node.schema is not None and node.schema.element is not None:
            # This generates the <[ id: int ]> part
            schema_header = self.encode_schema(node.schema.element, 0).strip()
        if schema_header:
            schema_header = schema_header + " "

        expected_child = node.schema.element if node.schema else None

        # --- COMPACT MODE ---
        if self.compact:
            items = []

            
            for el in node.elements:
                # IMPORTANT: We disable schema inclusion for elements to avoid duplication <...>
                # unless types mismatch drastically.
                val = self.encode(el, 0, include_schema=False).strip()

                # Check compatibility & Inject override if needed
                if not self._schemas_are_compatible(el.schema, expected_child):
                    label = self._get_type_label(el.schema)
                    tag = self._c(f"<{label}>", Colors.SCHEMA)
                    val = f"{tag} {val}"

                items.append(val)

            return ind + "[" + inner_meta + schema_header  + ",".join(items) + "]"

        # --- PRETTY MODE ---
        header = self._list_header(node)
        out = [ind + header]

        if inner_meta:
            out.append(" " * child_indent + inner_meta)

        if schema_header:
            out.append(" " * child_indent + schema_header)

        for el in node.elements:
            # IMPORTANT: Disable schema for children
            val = self.encode(
                el, child_indent - self.start_indent, include_schema=False
            )
            val = val.strip()

            # Check compatibility & Inject override if needed
            if not self._schemas_are_compatible(el.schema, expected_child):
                label = self._get_type_label(el.schema)
                tag = self._c(f"<{label}>", Colors.SCHEMA)
                val = f"{tag} {val}"

            out.append(" " * child_indent + val)

        out.append(ind + "]")
        return self._join(out, "\n")
    
  
    # -------------------------------------------------------------
    # RECORD: {key:value} -> (val1, val2) OR {key:value}
    # -------------------------------------------------------------
    def _record(self, node: Node, indent: int) -> str:
        inner_meta = self._meta_wrapped(node)

        parts = []
        if node.schema.fields:
            for field_def in node.schema.fields:
                field_node = node.fields.get(field_def.name)
                if field_node:
                    val = self.encode(
                        field_node, indent - self.start_indent, False
                    ).strip()
                    val = self._apply_type_tag(val, field_node.schema, field_def)
                    parts.append(val)
                else:
                    parts.append(self._c("null", Colors.NULL))
        else:
            parts.append(self._c("null", Colors.NULL))

        sep = ", " if not self.compact else ","
        return "(" + inner_meta + sep.join(parts) + ")"