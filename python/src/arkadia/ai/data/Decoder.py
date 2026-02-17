import re
from typing import Optional, Dict, List, Union, Any
from dataclasses import dataclass, field

from .Node import Node
from .Schema import Schema, SchemaKind
from .Meta import MetaInfo, Meta

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class Ansi:
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"


@dataclass
class DecodeError:
    message: str
    position: int
    context: str = ""
    schema: Schema | None = None
    node: Node | None = None

    def __repr__(self):
        parts = []

        # 1. Main Error Header
        parts.append(f"DecodeError: {self.message}")
        parts.append(f"  Position: {self.position}")

        # 2. Schema Information (if available)
        if self.schema is not None:
            # Use type_name (e.g., "User") or fallback to kind (e.g., "RECORD")
            s_name = self.schema.type_name or self.schema.kind.name
            parts.append(f"  Schema: {s_name}")

        # 3. Node Information (if available)
        if self.node:
            # Safely stringify value and truncate if too long
            val_str = str(self.node.value)
            if len(val_str) > 30:
                val_str = val_str[:27] + "..."
            parts.append(f"  Node Value: {val_str}")

        # 4. Context Visualization
        if self.context:
            # Replace actual newlines with literal '\n' text to keep the error block compact
            clean_ctx = self.context.replace("\n", "\\n").replace("\r", "")
            parts.append(f'  Context: "{clean_ctx}"')

        return "\n".join(parts)

    def __str__(self):
        # Simple one-liner for basic logging
        return f"[DecodeError] {self.message} (at pos {self.position})"



@dataclass
class DecodeWarning:
    message: str
    position: int
    context: str = ""
    schema: Schema | None = None
    node: Node | None = None

    def __repr__(self):
        parts = []

        # 1. Main Error Header
        parts.append(f"DecodeWarning: {self.message}")
        parts.append(f"     Position: {self.position}")

        # 2. Schema Information (if available)
        if self.schema is not None:
            # Use type_name (e.g., "User") or fallback to kind (e.g., "RECORD")
            s_name = self.schema.type_name or self.schema.kind.name
            parts.append(f"  Schema: {s_name}")

        # 3. Node Information (if available)
        if self.node:
            # Safely stringify value and truncate if too long
            val_str = str(self.node.value)
            if len(val_str) > 30:
                val_str = val_str[:27] + "..."
            parts.append(f"  Node Value: {val_str}")

        # 4. Context Visualization
        if self.context:
            # Replace actual newlines with literal '\n' text to keep the error block compact
            clean_ctx = self.context.replace("\n", "\\n").replace("\r", "")
            parts.append(f'  Context: "{clean_ctx}"')

        return "\n".join(parts)

    def __str__(self):
        # Simple one-liner for basic logging
        return f"[DecodeWarn] {self.message} (at pos {self.position})"



@dataclass
class DecodeResult:
    node: Node
    schema: Schema
    errors: list[DecodeError] = field(default_factory=list)
    warnings: list[DecodeWarning] = field(default_factory=list)

class Decoder:
    PRIMITIVES = {"string", "bool", "number", "null", "int", "float", "binary"}
    PRIMITIVES_MAPPING = {
        "string": "string",
        "bool": "bool",
        "number": "number",
        "null": "null",
        "int": "number",
        "int": "number",
        "float": "number",
        "binary": "binary",
    }
    MAX_ERRORS = 50

    def __init__(
        self,
        text: str,
        schema: str = "",
        remove_ansi_colors: bool = False,
        debug: bool = False,
    ):
        if remove_ansi_colors:
            text = ANSI_RE.sub("", text)

        self.text = schema + text
        self.debug = debug

        # 1. Cursor State
        self.i = 0
        self.line = 0
        self.col = 0

        # 2. Context State (Prefix Buffers)
        self._pending_meta: MetaInfo = MetaInfo()

        # 3. Hierarchy State
        self.node_stack: list[Node] = []
        self.schema_stack: list[Schema] = []
        self.errors: list[DecodeError] = []
        self.warnings: list[DecodeWarning] = []
        self.named_schemas: Dict[str, Schema] = {}


    # =========================================================
    # ENTRY
    # =========================================================

    def decode(self) -> DecodeResult:
        self._dbg("decode() start")
        self._parse_meta()

        root_schema_context: Optional[Schema] = None
        # 1. Schema Processing Loop
        # Handle definitions before the node (e.g., <x:int> or @User)
        while not self._eof():
            ch = self._peek()

            # Case: Inline Definition <x:int> (Anonymous)
            if ch == "<":
                root_schema_context = self._parse_schema_body()
                self._parse_meta()
                
                # Check lookahead: if next char is data start, break loop
                if self._peek() in ('(', '{', '['):
                    break
                
                continue

            # Case: Named Schema (@Name) OR Node Header (@Name)
            if ch == "@":
                # This parses "@Name" AND optionally "<...>" if present.
                schema = self._parse_schema_at_ref()
                self._parse_meta()
                
                # CHECK: What comes next?
                next_ch = self._peek()
                
                # If followed by another definition start, loop again.
                if next_ch == "@" or next_ch == "<":
                    continue
                
                # If followed by data ( (, {, [ ), this was the Root Node Header.
                root_schema_context = schema
                break
            
            # If neither < nor @, we hit the Data start directly.
            break

        # 2. Push Context (Apply the found schema to the root node parsing)
        if root_schema_context:
            self._push_schema(root_schema_context)

        # 3. Parse Root Node
        if self._eof():
            root_node = self._create_node(None)
        else:
            # Note: The cursor is now looking at the data (e.g. '(' or '{').
            root_node = self._parse_node()

        # 4. Cleanup Context
        if not root_schema_context is None:
            self._pop_schema()
            
            # Link schema if the node ended up being generic
            if root_node.schema is None or root_node.schema.is_any:
                 root_node.schema = root_schema_context

        else:
            root_schema_context = root_node.schema
                 


        # Final prefix scan (trailing comments)
        self._parse_meta()
        self._apply_meta(root_node)

        # Cleanup Stack (Just in case)
        self._pop_node()
        self._dbg("decode() end")

        return DecodeResult(
            node=root_node,
            schema=root_schema_context,
            errors=self.errors,
            warnings=self.warnings
        )

    # =========================================================
    # 5. SCHEMA DEFINITION PARSING
    # =========================================================


    def _parse_schema_at_ref(self) -> Schema:
        """
        Parses a reference @Name or definition @Name<...>.
        """
        self._advance(1) # consume '@'
        type_name = self._parse_ident()
        
        # We need to see if this is a Definition (@Name <...>) or just a Reference (@Name).
        # We scan comments/whitespace ahead to peek at the next character.
        self._skip_whitespace() # Note: This fills buffers with any comments between Name and <
        
        if self._peek() == "<":
            self._dbg(f"defining type {type_name}")
            
            # 1. Parse the body
            # _parse_schema_body will create a NEW schema and consume the prefix we just scanned
            schema = self._parse_schema_body(type_name)
  
            # If it wasn't detected as a list inside the body, ensure it's a record
            if schema.is_any: 
                schema.kind = SchemaKind.RECORD
            
            self.named_schemas[type_name] = schema
            return schema

        # --- It is a Reference ---
        self._dbg(f"referencing type {type_name}")

        # 1. Lookup
        if type_name in self.named_schemas:
            # Note: We return the EXISTING object. 
            # We do NOT apply pending prefix to it (it's already defined).
            return self.named_schemas[type_name]

        # 2. Forward Declaration / Lazy Placeholder
        # We return a new Record schema with this name.
        return Schema(kind=SchemaKind.RECORD, type_name=type_name, fields=[])


    def _parse_schema_body(self, type_name: str = "") -> Schema:
        """
        Parses the main schema block definition < ... >.
        """
        type_name_prefix = "@" + type_name if type_name else ""
        self._dbg(f"START parse_schema_body '<' {type_name_prefix}")

        if not self._expect("<"):
            schema = self._create_schema(SchemaKind.ANY, type_name)
            self._pop_schema()
            self._dbg(f"END parse_schema_body  '>' {type_name_prefix}")
            return schema

        # 1. Create Schema Object & Consume Context (Prefix from before '<')
        # We default to RECORD, but might change to LIST later.
        schema = self._create_schema(SchemaKind.RECORD, type_name)
        
        # 2. Parse Body Internals (The content inside < ... >)
        # We pass the existing schema object to populate it.
        self._parse_schema_body_content(schema, end_char=">")
        
        # 3. After all pop schema, _parse_schema_body() returns schema to push
        # again for the node if there is data after
        self._pop_schema()
        
        self._dbg(f"END parse_schema_body '>' {type_name_prefix}")

        return schema


    def _parse_schema_body_content(self, schema: Schema, end_char: str):
        """
        Internal helper to parse fields or list elements inside < ... > or [ ... ].
        """
        # # 1. Header Scan
        # self._parse_meta(schema)

        field_schema: Schema = None

        # 4. Fields Loop
        while not self._eof():
            self._parse_meta(schema)

            ch = self._peek()

            if ch == end_char:
                self._advance(1)
                break

            # 2. Check for LIST Schema: < [ ... ] >
            elif ch == "[":
                self._advance(1) # consume '['
                self._dbg("LIST schema begin")
                schema.kind = SchemaKind.LIST
                schema._fields_list = [] 
                schema._fields_map = {}
                self._apply_meta(schema)

                element_schema = Schema(SchemaKind.ANY)
                self._parse_schema_body_content(element_schema, end_char="]")
                schema.element = element_schema
                self._parse_meta(schema)
                if self._peek() == end_char:
                    self._advance(1)
                self._apply_meta(schema)
                return

            
            if self._peek() == ",":
                self._apply_meta(field_schema if field_schema else schema)
                self._advance(1)
                continue

            # B. Parse Field Name or Type Name
            name = self._parse_ident()
            if not name:
                self._add_error("Expected identifier")
                self._advance(1)
                continue

            self._skip_whitespace()

            # --- FIX: Detect Primitive List Definition [ int ] ---
            if name in self.PRIMITIVES and self._peek() != ":":
                schema.kind = SchemaKind.PRIMITIVE
                schema.type_name = self.PRIMITIVES_MAPPING[name]
                continue
            # -----------------------------------------------------
            
            if self._peek() == ":":
                self._advance(1) # consume ':'
                field_schema = self._parse_schema_type()
            else:
                field_schema = Schema(SchemaKind.PRIMITIVE, type_name="any")

            field_schema.name = name
            
            # 1. Apply comments found BEFORE the field name (prefix)
            self._apply_meta(field_schema)
            
            # --- FIX: TRAILING COMMENTS HANDLING ---
            # After parsing the type (e.g. 'int'), check for comments (e.g. /* pk */)
            # BEFORE moving to the comma.
            self._parse_meta(schema) 
            self._apply_meta(field_schema if field_schema else schema)
            # ---------------------------------------

            schema.add_field(field_schema)

        self._apply_meta(field_schema if field_schema else schema)

    def _parse_schema_type(self) -> Schema:
        """
        Parses a type signature string (e.g., 'int', '[string]', '@User', '@User<...>').
        Note: This is called AFTER the field name (e.g. "id: int").
        """
        # 1. Scan any comments before the type (e.g. id: /* comment */ int)
        self._parse_meta(self.schema)
        
        ch = self._peek()

        # Case A: List Shortform [int]
        if ch == "[":
            self._advance(1)
            # Create list schema
            lst = Schema(SchemaKind.LIST)
            self._apply_meta(lst) # Apply comments found before '['
            
            # Recurse for element
            lst.element = self._parse_schema_type()
            
            self._expect("]")
            return lst

        # Case B: Named Reference @User OR Definition @User<...>
        elif ch == "@":
            self._advance(1) # consume '@'
            name = self._parse_ident()
            
            # We need to peek ahead to see if this is a Reference (@User)
            # or a Definition with a body (@User<...>)
            self._parse_meta(self.schema) 
            
            if self._peek() == "<":
                self._dbg(f"Inline definition for @{name}")
                # Parse the body content
                schema = self._parse_schema_body(name)
                
                # If it parsed as generic ANY (empty <>), enforce RECORD
                if schema.is_any:
                    schema.kind = SchemaKind.RECORD
                
                # Register the definition
                self.named_schemas[name] = schema
                return schema

            # Just a Reference
            if name in self.named_schemas:
                return self.named_schemas[name]
            
            # Forward reference / Placeholder
            return Schema(SchemaKind.RECORD, type_name=name)

        # Case C: Inline Definition < ... > (Anonymous)
        elif ch == "<":
            return self._parse_schema_body()

        # Case D: Primitive or Identifier (int, string, User)
        else:
            name = self._parse_ident()
            
            # Check for Primitives
            if name in self.PRIMITIVES:
                s = Schema(SchemaKind.PRIMITIVE, 
                           type_name=self.PRIMITIVES_MAPPING[name])
                self._apply_meta(s) # Consume comments
                return s
                
            # Check for Named Types (implicit reference without @)
            if name in self.named_schemas:
                return self.named_schemas[name]
                
            # Fallback
            if not name:
                return Schema(SchemaKind.ANY)
                
            # Assume Reference to unknown type (Forward ref)
            return Schema(SchemaKind.RECORD, type_name=name)
        
    # =========================================================
    # 2. NODE DISPATCHER (High Level)
    # =========================================================

    def _parse_node(self) -> Node:
        """
        The main parsing hub.
        """
        # 1. Scan Prefix (Comments, Whitespace, Meta)
        self._parse_meta(self.node)

        if self._eof():
            self._add_error("Unexpected EOF while expecting a node")
            return self._create_node(None)

        ch = self._peek()
        # self._dbg(f"_parse_node dispatch on '{ch}'") # Optional: Very verbose

        node: Node
        # --- A. Schema Context Switches (@ or <) ---
        if ch == "@":
            node = self._parse_node_with_schema_ref()
        
        elif ch == "<":
            node = self._parse_node_with_inline_schema()

        # --- B. Structures ---
        elif ch == "[":
            node = self._parse_list()
        
        elif ch == "(":
            node = self._parse_positional_record()
        
        elif ch == "{":
            node = self._parse_named_record()

        # --- C. Primitives ---
        elif ch == '"':
            self._dbg("Dispatch: String")
            node = self._parse_string()
        
        elif ch.isdigit() or ch == '-':
            self._dbg("Dispatch: Number")
            node = self._parse_number()
        
        elif ch.isalpha() or ch == '_':
            self._dbg("Dispatch: RawString/Ident")
            node = self._parse_raw_string()

        else:
            self._add_error(f"Unexpected character '{ch}'")
            self._advance(1)
            node = self._create_node(None)

        self._apply_meta(node)
        return node
    
    def _parse_node_with_schema_ref(self) -> Node:
        """
        Parses a node prefixed with a reference: @Type ...
        """
        self._dbg("Start Node with Ref (@)")
        
        # 1. Parse the Schema Reference
        # Note: This consumes the prefix scanned in _parse_node into the Schema object!
        # If that's undesired (prefix belongs to value), we need different logic, 
        # but usually @Type is the start of the node definition.
        specific_schema = self._parse_schema_at_ref()
        
        # 2. Push Context
        self._push_schema(specific_schema)
        
        # 3. Parse the actual Value
        # _parse_node is recursive, so it handles scanning the gap between @Type and Value
        node = self._parse_node()
        
        # 4. Cleanup
        self._pop_schema()
        
        # 5. Link Schema 
        # (Explicitly override because _parse_node used the stack, but valid to reinforce)
        node.schema = specific_schema
        return node


    def _parse_node_with_inline_schema(self) -> Node:
        """
        Parses a node prefixed with an inline definition: <...> ...
        """
        self._dbg("Start Node with Inline (<)")
        
        # 1. Parse the Inline Schema
        specific_schema = self._parse_schema_body()
        
        # 2. Push Context
        self._push_schema(specific_schema)
        
        # 3. Parse Value
        node = self._parse_node()
        
        # 4. Cleanup
        self._pop_schema()
        
        node.schema = specific_schema
        return node

    # =========================================================
    # 3. STRUCTURE PARSERS (Complex Types)
    # =========================================================

    def _parse_list(self) -> Node:
        """
        Parses a List structure [ ... ].
        """
        self._dbg("Start LIST [")
        self._advance(1) # consume '['
        
        # 1. Create Node (Consumes pending prefix)
        node = self._create_node()
        node.elements = []

        if node.schema.kind != SchemaKind.LIST:
            node.schema.kind = SchemaKind.LIST
            node.schema.type_name = "list"
            node.schema.element = Schema(SchemaKind.ANY)
        
        # 2. Determine Child Context
        # If parent is LIST, children use the 'element' schema.
        # If parent is ANY/RECORD, children default to ANY.
        parent_schema = node.schema
        child_schema = Schema(SchemaKind.ANY)
        
        if parent_schema and parent_schema.is_list and parent_schema.element:
            child_schema = parent_schema.element
        

        child_node: Node = None
        # 3. Loop
        while True:
            self._parse_meta(node) # Check for comments/end
            
            # Push Child Context
            self._push_schema(child_schema)

            if self._eof():
                self._add_error("Unexpected EOF: List not closed, expected ']'")
                break

            if self._peek() == "]":
                self._apply_meta(child_node if child_node is not None else node)
                self._advance(1)
                break
                
            if self._peek() == ",":
                self._apply_meta(child_node if child_node is not None else node)
                self._advance(1)
                continue
            
            # Parse Child
            child_node = self._parse_node()
            node.elements.append(child_node)

            if parent_schema.element and parent_schema.element.is_any:
                parent_schema.element = child_node.schema
            
            # pop node
            self._apply_meta(child_node if child_node is not None else node)
            self._pop_node()
            self._pop_schema()

        # Pop Child Context
        self._pop_schema()
        
        self._dbg("End LIST ]")
        return node


    def _parse_positional_record(self) -> Node:
        """
        Parses a Positional Record ( val1, val2 ).
        Maps values to schema fields by index if schema exists.
        If no schema exists, infers fields as _0, _1, etc.
        """
        self._dbg("Start RECORD (")
        self._advance(1) # consume '('
        
        node = self._create_node()
        
        # --- FIX: TYPE INFERENCE ---
        # Force RECORD type since we are in parentheses.
        if node.schema.kind != SchemaKind.RECORD:
            node.schema.kind = SchemaKind.RECORD
            node.schema.type_name = "any"
        # ---------------------------
        
        index = 0
        # Capture pre-defined fields to distinguish between validation and inference.
        # We convert to list to freeze the state before we start adding inferred fields.
        predefined_fields = list(node.schema.fields) if node.schema.fields else []

        val_node: Any = None
        
        while not self._eof():
            self._parse_meta(node)

            if self._peek() == ")":
                self._apply_meta(val_node if val_node is not None else node)
                self._advance(1)
                break
            
            if self._peek() == ",":
                self._apply_meta(val_node if val_node is not None else node)
                self._advance(1)
                continue

            # Determine Field Context (for validation/schema propagation)
            field_schema = Schema(SchemaKind.ANY)

            if index < len(predefined_fields):
                field_schema = predefined_fields[index]

            # Parse Value
            self._push_schema(field_schema)
            val_node = self._parse_node()

            # --- FIX: MAPPING & INFERENCE ---
            if index < len(predefined_fields):
                # Case A: Schema exists -> Map to existing field name
                name = predefined_fields[index].name
                node.fields[name] = val_node
            else:
                # Case B: Schema missing (or overflow) -> Infer new field '_Index'
                name = f"_{index}"
                
                # Create and inject new field definition into the parent schema
                inferred_field = Schema(val_node.schema.kind, type_name=val_node.schema.type_name)
                inferred_field.name = name
                node.schema.add_field(inferred_field)
                
                # Store in fields map
                node.fields[name] = val_node
            # --------------------------------

            self._apply_meta(val_node if val_node is not None else node)
            self._pop_node()
            self._pop_schema()
            index += 1

        self._dbg("End RECORD )")
        return node


    def _parse_named_record(self) -> Node:
        """
        Parses a Named Record { key: val, ... }.
        Uses O(1) lookup via _fields_map.
        """
        self._dbg("Start NAMED RECORD {")
        self._advance(1) # consume '{'
        
        node = self._create_node()
        node.fields = {}
        
        # Ensure the node is treated as a RECORD
        if node.schema.kind != SchemaKind.RECORD:
            node.schema.kind = SchemaKind.RECORD
            node.schema.type_name = "any"
        
        current_schema = node.schema
        val_node: Node = None
        
        while not self._eof():
            self._parse_meta(node)

            if self._peek() == "}":
                self._apply_meta(val_node if val_node is not None else node)
                self._advance(1)
                break
            
            if self._peek() == ",":
                self._apply_meta(val_node if val_node is not None else node)
                self._advance(1)
                continue

            # 1. Parse Key
            key_name = self._parse_ident()
            if not key_name:
                if self._peek() == '"':
                    key_name = self._read_quoted_string()
                else:
                    self._add_error("Expected key in record")
                    self._advance(1)
                    continue

            self._skip_whitespace()
            self._expect(":")
            
            # 2. Determine Field Context (OPTIMIZED)
            field_schema = Schema(SchemaKind.ANY)

            if current_schema and current_schema.is_record:
                if key_name in current_schema._fields_map:
                    field_schema = current_schema._fields_map[key_name]

            # 3. Parse Value
            self._push_schema(field_schema)
            val_node = self._parse_node()

            if (not val_node.schema.is_any 
                and key_name in current_schema._fields_map 
                and current_schema._fields_map[key_name].is_any):
                # """
                # For schema that has some any type inside
                #  <ab>
                # {
                #     ab:  ["a", "b", "c", 3]
                # }
                # """
                val_node.schema.name = key_name
                current_schema.replace_field(val_node.schema)
            
            # --- FIX: SCHEMA INFERENCE ---
            # If we are parsing a dynamic record (the schema doesn't have this field yet),
            # we must add the field definition to the schema so it matches the node structure.
            if key_name not in node.schema._fields_map:
                # Create a new field definition based on the parsed value's type
                inferred_field = Schema(val_node.schema.kind, type_name=val_node.schema.type_name)
                inferred_field.name = key_name
                # Add to the parent schema
                node.schema.add_field(inferred_field)
            # -----------------------------

            # Store in fields
            node.fields[key_name] = val_node
            self._apply_meta(val_node if val_node is not None else node)
            # Cleanup stack
            self._pop_node()
            self._pop_schema()

        self._dbg("End NAMED RECORD }")
        return node
    

    # =========================================================
    # 6. PREFIX & META PARSING (Context)
    # =========================================================

    def _parse_meta(self, obj: Union[Node, Schema] = None):
        """
        Consumes Whitespace, Comments, and Modifiers ($ # ! /.../) before a node
        and after the node.
        Populates  and self._pending_meta._comments
        """
        while not self._eof():
            self._skip_whitespace()
            
            ch = self._peek()
            next_ch = self._peek_next()

            # 1. Block Comment /* ... */
            if ch == '/' and next_ch == '*':
                self._pending_meta.comments.append(self._parse_comment_block())
                continue

            # 2. Meta Block / ... / (Must not be /*)
            if ch == '/' and next_ch != '*':
                # Parse the block
                self._parse_meta_block(obj)
                continue

            # 3. Inline Modifiers
            if ch in ('$', '#', '!'):
                self._parse_modifier_inline()
                continue

            # If none of the above, we are at the start of a Node or Schema
            break


    def _parse_comment_block(self):
        """
        Consumes a /* ... */ block and appends it to self._pending_meta.comments.
        Handles nested comments.
        """
        self._dbg("START block comment")
        self._advance(2) # consume /*
        
        nesting_level = 1
        content_chars = []
        
        while not self._eof() and nesting_level > 0:
            ch = self.text[self.i]
            
            # Handle Escape
            if ch == '\\':
                self._advance(1)
                if not self._eof():
                    content_chars.append(self._next())
                continue
                
            # Handle Nesting Open /*
            if ch == '/' and self._peek_next() == '*':
                nesting_level += 1
                self._advance(2)
                content_chars.append("/*")
                continue
                
            # Handle Nesting Close */
            if ch == '*' and self._peek_next() == '/':
                nesting_level -= 1
                self._advance(2)
                if nesting_level > 0:
                    content_chars.append("*/")
                continue
                
            # Normal char
            content_chars.append(ch)
            self._advance(1)

        if nesting_level > 0:
            self._add_error("Unterminated comment (expected '*/')")
            
        final_comment = "".join(content_chars).strip()
        self._dbg(f"END block comment '{final_comment[:30] + ('...' if len(final_comment) > 30 else '')}'")
        return final_comment


    def _parse_modifier_inline(self):
        """
        Dispatches inline modifiers ($attr, #tag, !flag).
        Updates self._pending_meta.
        """
        ch = self._peek()
        
        if ch == '$':
            self._parse_meta_attribute(self._pending_meta)
        elif ch == '#':
            self._parse_meta_tag(self._pending_meta)
        elif ch == '!':
            self._parse_meta_flag(self._pending_meta)
        else:
            # Should not happen if called correctly
            self._advance(1)


    def _parse_meta_block(self,  obj: Optional[Union[Node, Schema]] = None) -> MetaInfo:
        """
        Parses a / ... / block. 
        """
        self._expect("/")
        self._dbg("START meta header /.../")
        
        meta = MetaInfo()
        
        while not self._eof():
            self._skip_whitespace()
            ch = self._peek()
            next_ch = self._peek_next()

            if ch == '/' and next_ch == '*':
                meta.comments.append(self._parse_comment_block())
                continue

            # Check for block end
            if ch == '/':
                self._advance(1)
                break

            # Explicit modifiers
            if ch == '$':
                self._parse_meta_attribute(meta)
                continue
            if ch == '#':
                self._parse_meta_tag(meta)
                continue
            if ch == '!':
                self._parse_meta_flag(meta)
                continue

            # Implicit Attribute (Legacy support: key=value without $)
            if ch.isalnum() or ch == '_':
                key = self._parse_ident()
                val = True
                
                self._skip_whitespace()
                if self._peek() == '=':
                    self._advance(1)
                    val = self._parse_primitive_value()
                
                self._add_warning(f"Implicit attribute '{key}'. Use '${key}' instead.")
                if meta.attr is None: meta.attr = {}
                meta.attr[key] = val
                continue
            
            # Error or Unexpected
            self._add_error(f"Unexpected token in meta block: {ch}")
            self._advance(1)

        if obj:
            obj.apply_meta(meta)
        else:
            self._add_warning(f"There is no parent to add the meta block '{meta}'")
            self._pending_meta.apply_meta(meta)

        self._dbg("END meta header")
        return meta


    def _parse_meta_attribute(self, meta: MetaInfo):
        """Parses $key=value."""
        self._advance(1) # consume $
        
        key = self._parse_ident() # Using standard ident parser
        val = True
        
        self._skip_whitespace()
        if self._peek() == '=':
            self._advance(1)
            val = self._parse_primitive_value()
            
        if meta.attr is None: meta.attr = {}
        meta.attr[key] = val
        self._dbg(f"Meta Attr: ${key}={val}")


    def _parse_meta_tag(self, meta: MetaInfo):
        """Parses #tag."""
        self._advance(1) # consume #
        tag = self._parse_ident()
        
        if meta.tags is None: meta.tags = []
        meta.tags.append(tag)
        self._dbg(f"Meta Tag: #{tag}")


    def _parse_meta_flag(self, meta: MetaInfo):
        """Parses !flag (e.g. !required)."""
        self._advance(1) # consume !
        flag = self._parse_ident()
        
        if flag == "required":
            meta.required = True
            self._dbg("Meta Flag: !required")
        else:
            self._add_warning(f"Unknown flag: !{flag}")
    
    
    # =========================================================
    # HELPERS
    # =========================================================

    def _parse_ident(self) -> str:
        """Parses a standard identifier [a-zA-Z_][a-zA-Z0-9_]*"""
        self._skip_whitespace() # Identifiers shouldn't have leading space usually, but safe to skip
        
        start_idx = self.i
        if self._eof(): return ""
        
        # First char check
        if not (self.text[self.i].isalpha() or self.text[self.i] == '_'):
            return ""
            
        self._advance(1)
        
        # Rest of chars
        while not self._eof():
            ch = self.text[self.i]
            if ch.isalnum() or ch == '_':
                self._advance(1)
            else:
                break
                
        return self.text[start_idx : self.i]

    # =========================================================
    # 4. PRIMITIVE PARSERS (Simple Values)
    # =========================================================

    def _parse_string(self) -> Node:
        """
        Parses a quoted string into a Node.
        """
        value = self._read_quoted_string()
        return self._create_node(value)

    def _parse_number(self) -> Node:
        """
        Parses integers and floats into a Node.
        """
        value = self._read_number()
        return self._create_node(value)

    def _parse_raw_string(self) -> Node:
        """
        Parses unquoted strings (identifiers, enums, booleans) into a Node.
        Handles: true, false, null.
        """
        raw = self._parse_ident()
        
        # 1. Resolve Keywords
        if raw == "true":
            value = True
        elif raw == "false":
            value = False
        elif raw == "null":
            value = None
        else:
            value = raw

        return self._create_node(value)

    def _parse_primitive_value(self) -> Any:
        """
        Helper that parses a raw Python value (int/bool/str/float) WITHOUT creating a Node.
        Used exclusively by Metadata Attribute parsers ($key=value).
        """
        ch = self._peek()
        if ch is None:
            return None

        # 1. String
        if ch == '"':
            return self._read_quoted_string()

        # 2. Number (digit or negative sign)
        if ch.isdigit() or ch == '-':
            return self._read_number()

        # 3. Boolean / Null / Unquoted String
        raw = self._parse_ident()
        if raw == "true":
            return True
        elif raw == "false":
            return False    
        elif raw == "null":
            return None
        
        return raw

    # =========================================================
    # LOW-LEVEL READERS (Internal Helpers)
    # =========================================================

    def _read_quoted_string(self) -> str:
        """Reads content between double quotes, handling simple escapes."""
        self._expect('"')
        
        start = self.i
        result = []
        
        while not self._eof():
            ch = self.text[self.i]
            
            if ch == '"':
                break
                
            if ch == '\\':
                self._advance(1) # Skip backslash
                if self._eof(): break
                escaped = self.text[self.i]
                
                # Simple escape mapping
                if escaped == 'n': result.append('\n')
                elif escaped == 't': result.append('\t')
                elif escaped == 'r': result.append('\r')
                elif escaped == '"': result.append('"')
                elif escaped == '\\': result.append('\\')
                else: result.append(escaped) # Fallback
                
                self._advance(1)
            else:
                result.append(ch)
                self._advance(1)
        
        self._expect('"')
        return "".join(result)

    def _read_number(self) -> Union[int, float]:
        """Reads a number token and converts it to int or float."""
        start_idx = self.i
        
        # 1. Sign
        if self._peek() == '-':
            self._advance(1)

        # 2. Integer Part
        while not self._eof() and self._peek().isdigit():
            self._advance(1)

        # 3. Fraction Part
        is_float = False
        if self._peek() == '.':
            is_float = True
            self._advance(1)
            while not self._eof() and self._peek().isdigit():
                self._advance(1)

        # 4. Exponent Part
        if self._peek() in ('e', 'E'):
            is_float = True
            self._advance(1)
            if self._peek() in ('+', '-'):
                self._advance(1)
            while not self._eof() and self._peek().isdigit():
                self._advance(1)

        raw_num = self.text[start_idx : self.i]
        
        try:
            return float(raw_num) if is_float else int(raw_num)
        except ValueError:
            self._add_error(f"Invalid number format: {raw_num}")
            return 0


    # =========================================================
    # SCHEMA
    # =========================================================

    @property
    def schema(self):
        return self.schema_stack[-1] if self.schema_stack else None

    def _create_schema(self, kind: SchemaKind = SchemaKind.ANY, type_name: str = "") -> Schema:
        """
        1. Creates a NEW Schema.
        2. Consumes buffers via _apply_meta_to_schema.
        3. Pushes to stack.
        """
        # Create
        schema = Schema(kind, type_name=type_name)
        
        # Consume Buffers (Strictly for Schema)
        self._apply_meta(schema)
        
        # Push to Stack
        self._push_schema(schema)
        
        return schema


    def _push_schema(self, schema: Schema):
        """Pushes a Schema onto the stack."""
        self.schema_stack.append(schema)
        self._dbg(f"PUSH SCHEMA {schema}")

    def _pop_schema(self) -> Optional[Schema]:
        
        """Removes the current Schema from the stack."""
        self._dbg(f"POP SCHEMA {self.schema}")
        schema = self.schema_stack.pop() if self.schema_stack else None
        if schema and schema.is_list:
            schema.apply_meta(schema.element)
            schema.element.clear_meta()

        return schema


    # =========================================================
    # NODE
    # =========================================================

    @property
    def node(self):
        return self.node_stack[-1] if self.node_stack else None

    def _push_node(self, node: Node):
        """Pushes a Node onto the stack."""
        self.node_stack.append(node)
        self._dbg(f"PUSH NODE {node}")

    def _pop_node(self) -> Optional[Node]:
        """Removes the current Node from the stack."""
        self._dbg(f"POP NODE {self.node}")
        node = self.node_stack.pop() if self.node_stack else None
        return node

    def _create_node(self, value: Any = None) -> Node:
        current_schema = self.schema
        if current_schema is None:
            current_schema = Schema(SchemaKind.ANY)
            self._push_schema(current_schema)

        final_schema = current_schema

        # Handling Value Types
        if value is not None:
            inferred_schema = None
            if isinstance(value, bool): inferred_schema = Schema(SchemaKind.PRIMITIVE, type_name="bool")
            elif isinstance(value, int): inferred_schema = Schema(SchemaKind.PRIMITIVE, type_name="number")
            elif isinstance(value, float): inferred_schema = Schema(SchemaKind.PRIMITIVE, type_name="float")
            elif isinstance(value, str): inferred_schema = Schema(SchemaKind.PRIMITIVE, type_name="string")
            
            # Compatibility Logic
            is_compatible = False
            if current_schema.kind == SchemaKind.ANY:
                is_compatible = True
                final_schema = inferred_schema
            elif current_schema.type_name == inferred_schema.type_name:
                is_compatible = True
            elif current_schema.type_name == "number" and inferred_schema.type_name in ("int", "float"):
                is_compatible = True
            
            if not is_compatible:
                final_schema = inferred_schema
        
        else:
            # Value is None.
            # If context is a Structure (Record/List), we presume we are starting to parse it.
            # So we KEEP the current schema.
            if current_schema.is_record or current_schema.is_list:
                final_schema = current_schema
            elif current_schema.is_any:
                final_schema = Schema(SchemaKind.PRIMITIVE, type_name="null")
            else:
                # Context is strict primitive (e.g. "int"), but value is None (null).
                # We interpret this as a NULL value overriding the type (or matching a nullable).
                final_schema = Schema(SchemaKind.PRIMITIVE, type_name="null")

        node = Node(schema=final_schema, value=value)
        self._apply_meta(node)
        self._push_node(node)
        return node


    # =========================================================
    # STATE & CONTEXT MANAGEMENT
    # =========================================================

    def _apply_meta(self, obj: Union[Node, Schema]):
        # 1. Apply Metadata ($attr, #tag, !required)
        obj.apply_meta(self._pending_meta)
        self._pending_meta = MetaInfo()  # Clear buffer

    # =========================================================
    # CORE NAVIGATION (THE ONLY FUNCTION TO UPDATE POS)
    # =========================================================

    def _advance(self, n: int = 1) -> str:
        """
        Advances the cursor by N characters, updating line and col counters instantly.
        Returns the LAST character consumed.
        """
        last_char = ""
        for _ in range(n):
            if self.i >= len(self.text):
                break

            char = self.text[self.i]
            last_char = char

            # Update State
            if char == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1

            self.i += 1

        return last_char


    # =========================================================
    # CHARS WHITESPACE HANDLING
    # =========================================================

    def _skip_whitespace(self):
        """
        PURE whitespace skip.
        It does NOT consume comments. It stops at '/'.
        Use this when you want to advance past spaces but KEEP comments
        in the stream for 'scan_comments' to pick up.
        """
        while not self._eof():
            ch = self._peek()
            if ch.isspace():
                self._advance(1)
            else:
                break


    # =========================================================
    # HELPERS
    # =========================================================

    def _eof(self) -> bool:
        return self.i >= len(self.text)

    def _expect(self, ch: str) -> bool:
        """
        Expects a specific character.
        NOTE: This calls scan_comments() internally to skip over comments
        that act as whitespace/noise between tokens.
        It DISCARDS those comments.
        """
        if self._peek() != ch:
            self._add_error(f"Expected '{ch}', got '{self._peek()}'")
            return False
        self._next()
        return True

    def _peek(self) -> Optional[str]:
        return None if self._eof() else self.text[self.i]

    def _peek_next(self) -> Optional[str]:
        return self.text[self.i + 1] if self.i + 1 < len(self.text) else None

    def _next(self) -> str:
        ch = self._peek()
        self._advance(1)
        return ch

    def _add_error(self, msg: str):
        if len(self.errors) >= self.MAX_ERRORS:
            return
        self._dbg(f"ERROR: {msg}")
        self.errors.append(
            DecodeError(msg, self.i, "", self.node, self.schema)
        )

    def _add_warning(self, msg: str):
        self._dbg(f"WARNING: {msg}")
        self.warnings.append(
            DecodeWarning(msg, self.i, "", self.node, self.schema)
        )

    def _should_abort(self) -> bool:
        return len(self.errors) >= self.MAX_ERRORS

    # =========================================================
    # DEBUG
    # =========================================================

    def _dbg(self, msg: str):
        if not self.debug:
            return

        loc_str = f"{self.line+1}:{self.col+1}"

        depth = len(self.node_stack)
        tree_prefix = ""
        if depth > 0:
            tree_prefix = f"{Ansi.DIM}" + ("│ " * (depth - 1)) + "├─ " + f"{Ansi.RESET}"

        start = max(0, self.i - 10)
        end = min(len(self.text), self.i + 11)
        # Safe slicing and replacement
        raw_before = self.text[start : self.i].rjust(10).replace("\n", "↩︎")
        raw_current = (self.text[self.i : self.i + 1] or " ").replace("\n", "↩︎").replace(" ", "·").replace("\t", "→")
        raw_after = self.text[self.i + 1 : end].ljust(10).replace("\n", "↩︎")

        context = f"{Ansi.DIM}{raw_before}{Ansi.RESET}{Ansi.YELLOW}{raw_current}{Ansi.RESET}{Ansi.DIM}{raw_after}{Ansi.RESET}"

        msg_color = Ansi.RESET
        if "ERROR" in msg:
            msg_color = Ansi.RED
        if "WARNING" in msg:
            msg_color = Ansi.YELLOW
        elif "→" in msg:
            msg_color = Ansi.GREEN
        elif "PUSH" in msg or "POP" in msg:
            msg_color = Ansi.MAGENTA
        elif "START" in msg or "END" in msg:
            msg_color = Ansi.DIM

        print(
            f"{Ansi.CYAN}|{loc_str:>8}|{Ansi.RESET}{Ansi.DIM} {Ansi.RESET}{context}{Ansi.DIM}{Ansi.CYAN}|{Ansi.RESET} {Ansi.YELLOW}{tree_prefix}{Ansi.YELLOW}@{depth}{Ansi.RESET} {Ansi.DIM}|{Ansi.RESET} {msg_color}{msg}{Ansi.RESET}"
        )