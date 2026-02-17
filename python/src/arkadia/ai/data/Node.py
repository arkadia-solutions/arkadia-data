from typing import Any, Dict, List, Optional
from .Schema import Schema, SchemaKind
from .Config import Config
from .Meta import Meta, MetaInfo
import json
import re


class Node(Meta):
    """
    Canonical runtime data object for AI.DATA.

    A Node always refers to a Schema which defines how data should be interpreted.

    Forms:
    - primitive:   value = 1,  "Aga",  True
    - record:      fields = { key: Node }
    - list:        elements = [Node, Node]

    Only values allowed by the Schema should be stored here.
    """

    def __init__(
        self,
        schema: Schema,
        *,
        name: Optional[str] = None,
        # primitive: 42, "A", True
        value: Any = None,
        # named: {"a": Node, "b": Node}
        fields: Optional[Dict[str, "Node"]] = None,
        # list: [Node,Node,...]
        elements: Optional[List["Node"]] = None,

        # list of comments associated with this node /* comment */ /* comment2 */
        comments: Optional[List[str]] = None,
        # Meta information (Runtime meta from data block) e.g. / @size=10 / -> {"size": 10}
        attr: Optional[Dict[str, Any]] = None,
        # Tags for meta #a #b #c
        tags: Optional[List[str]] = None,
    ):
        super().__init__(
            comments=comments, 
            attr=attr, 
            tags=tags)
        
        self.schema = schema
        self.name = name or ""

        self.value = value
        self.fields = fields or {}
        self.elements = elements or []


    # -----------------------------------------------------------
    # Introspection helpers
    # -----------------------------------------------------------

    @property
    def is_primitive(self):
        return self.schema is not None and self.schema.is_primitive

    @property
    def is_record(self):
        return self.schema is not None and self.schema.is_record

    @property
    def is_list(self):
        return self.schema is not None and self.schema.is_list

    # -----------------------------------------------------------
    #  Meta
    # -----------------------------------------------------------

    def clear_meta(self):
        self.clear_common_meta()

    def apply_meta(self, info: MetaInfo):
        """
        Applies ALL metadata, including constraints (!required).
        """
        # 1. Apply common stuff (meta dict, comments)
        self.apply_common_meta(info)

    # -----------------------------------------------------------
    # Dict
    # -----------------------------------------------------------

    def dict(self) -> Any:
        """
        Recursively converts the Node into a standard Python dictionary/list/primitive.
        Useful for debugging or interfacing with standard JSON libraries.
        """
        # print("Converting Node to dict...", self.schema, 
        #       "\n", 
        #       self.is_primitive,
        #       "\n", 
        #       self.is_list,
        #       "\n",
        #       "-" * 120)
        
        if self.is_primitive:
            return self.value

        if self.is_list:
            return [element.dict() for element in self.elements]

        if self.is_record:
            return {key: field_node.dict() for key, field_node in self.fields.items()}

        return self.value
    
    # -----------------------------------------------------------
    # json
    # -----------------------------------------------------------

    def json(self, indent: int = 2, colorize: bool = False) -> str:
        """
        Converts the Node to a JSON string.

        Args:
            indent (int): Number of spaces for indentation.
            colorize (bool): If True, applies ANSI colors to keys, strings, numbers, etc.
        """
        # 1. Convert to standard python dict
        data = self.dict()

        # 2. Dump to string
        json_str = json.dumps(data, indent=indent, ensure_ascii=False)

        if not colorize:
            return json_str

        # 3. Apply Colors (Simple Regex Tokenizer)
        # Using ANSI codes matching your Encoder class:
        # STRING = Green, NUMBER = Blue, BOOL = Magenta, NULL = Gray, KEY = Yellow

        RESET = "\033[0m"
        STRING = "\033[92m"
        NUMBER = "\033[94m"
        BOOL = "\033[95m"
        NULL = "\033[90m"
        KEY = "\033[93m"

        def replace_match(match):
            s = match.group(0)

            # Key ("key": )
            if re.match(r'^".*":$', s.strip()):
                return f"{KEY}{s}{RESET}"

            # String value ("value")
            if s.startswith('"'):
                return f"{STRING}{s}{RESET}"

            # Boolean
            if s in ("true", "false"):
                return f"{BOOL}{s}{RESET}"

            # Null
            if s == "null":
                return f"{NULL}{s}{RESET}"

            # Number (integers or floats)
            return f"{NUMBER}{s}{RESET}"

        # Regex to capture JSON tokens:
        # 1. Keys (quoted string followed by colon)
        # 2. String values
        # 3. Booleans/Null
        # 4. Numbers
        token_pattern = r'(".*?"\s*:)|(".*?")|\b(true|false|null)\b|(-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)'

        return re.sub(token_pattern, lambda m: replace_match(m), json_str)

    # -----------------------------------------------------------

    def encode(self, config: Config = {
        "indent": 2,
    }) -> str:
        """
        Debug fallback. Real encoder is in encoder.py.
        """
        from .Encoder import Encoder
        return Encoder(config).encode(self)

    def __repr__(self):
        """
        Technical debug representation.
        Format: <Node(KIND:type) value/len=... details...>
        """
        # 1. Type Info
        if self.schema:
            kind = self.schema.kind.name
            type_name = self.schema.type_name
            
            # Complex type display
            if self.is_list:
                el_type = self.schema.element.type_name if self.schema.element else "any"
                type_label = f"LIST[{el_type}]"
            elif self.is_record and type_name not in ("record", "any"):
                type_label = f"RECORD:{type_name}"
            else:
                type_label = f"{kind}:{type_name}"
        else:
            type_label = "UNKNOWN"


        header = f"<Node({type_label})"

        # 2. Content Info
        content = []
        
        if self.is_primitive:
            # Show value, truncated if necessary
            v = repr(self.value)
            if len(v) > 50: v = v[:47] + "..."
            content.append(f"val={v}")
            
        elif self.is_list:
            # Show count
            count = len(self.elements)
            content.append(f"len={count}")
            
        elif self.is_record:
            # Show keys summary
            keys = list(self.fields.keys())
            if len(keys) > 3:
                keys_str = ", ".join(keys[:3]) + ", ..."
            else:
                keys_str = ", ".join(keys)
            content.append(f"fields=[{keys_str}]")
        else:
            v = repr(self.value)
            if len(v) > 50: v = v[:47] + "..."
            content.append(f"val={v}")

        # 3. Meta Indicators (Concise)
        if self.comments:
            content.append(f"comments={len(self.comments)}")
        
        # Attributes
        current_attr = getattr(self, 'attr', getattr(self, 'meta', {}))
        if current_attr:
            content.append(f"attr={list(current_attr.keys())}")

        # Tags
        current_tags = getattr(self, 'tags', [])
        if current_tags:
            content.append(f"tags={current_tags}")

        # Assemble
        details_str = " " + " ".join(content) if content else ""
        return f"{header}{details_str}>"
