from typing import Optional, List, Dict, Union, Any
from enum import Enum
from .Meta import Meta, MetaInfo
from .Config import Config

class SchemaKind(Enum):
    PRIMITIVE = "primitive"  # int, string, bool, null, etc.
    RECORD = "record"  # User, Point, or anonymous <...>
    LIST = "list"  # Array/Sequence of elements
    DICT = "dict"  # Future-proofing: Key-Value pairs
    ANY = "any"  # Fallback


class Schema(Meta):
    def __init__(
        self,
        kind: SchemaKind,
        *,
        type_name: str = None,
        name: Optional[str] = None,
        fields: List["Schema"] = None,
        element: "Schema" = None,
        key: "Schema" = None,
        value: "Schema" = None,

        # meta
        # list of comments associated with this node /* comment */ /* comment2 */
        comments: Optional[List[str]] = None,
        # Meta information (Runtime meta from data block) e.g. / @size=10 / -> {"size": 10}
        attr: Optional[Dict[str, Any]] = None,
        # Tags for meta #a #b #c
        tags: Optional[List[str]] = None,
        # is it required?
        required: bool = False
    ):
        super().__init__(
            comments=comments, 
            attr=attr, 
            tags=tags)
        
        self.kind = kind
        self.type_name = type_name or "any"
        self.name = name or ""

        self.element = element
        self.key = key
        self.value = value
        self.required = required

        self._fields_list: List["Schema"] = []
        self._fields_map: Dict[str, "Schema"] = {}

        if fields:
            for f in fields:
                self.add_field(f)

    @property
    def is_primitive(self) -> bool: return self.kind == SchemaKind.PRIMITIVE
    @property
    def is_record(self) -> bool: return self.kind == SchemaKind.RECORD
    @property
    def is_list(self) -> bool: return self.kind == SchemaKind.LIST
    @property
    def is_any(self) -> bool: return (
        self.kind == SchemaKind.ANY 
        or (self.type_name == "any" and self.kind == SchemaKind.PRIMITIVE)
        or (self.type_name == "any" and self.kind == SchemaKind.RECORD)

    )

    def clear_fields(self):
        self._fields_list: List["Schema"] = []
        self._fields_map: Dict[str, "Schema"] = {}

    def add_field(self, field: "Schema"):
        if self.kind != SchemaKind.RECORD:
            self.kind = SchemaKind.RECORD
        f_name = field.name or str(len(self._fields_list))
        field.name = f_name
        self._fields_list.append(field)
        self._fields_map[f_name] = field

    def __getitem__(self, key: Union[int, str]) -> "Schema":
        if not self.is_record: raise TypeError(f"Schema kind {self.kind} is not subscriptable.")
        if isinstance(key, int): return self._fields_list[key]
        return self._fields_map[key]
    

    def __len__(self): return len(self._fields_list)

    def __bool__(self):
        return True

    @property
    def fields(self) -> List["Schema"]: return self._fields_list

    # -----------------------------------------------------------
    # Replace field by name
    # -----------------------------------------------------------


    def replace_field(self, field: "Schema"):
        """
        Replaces an existing field with a new definition based on field.name.
        Preserves the original order in the fields list.
        If the field does not exist, it appends it (like add_field).
        """
        f_name = field.name
        if not f_name:
            raise ValueError("Cannot replace a field without a name.")

        if f_name in self._fields_map:
            # 1. Retrieve the old object to find its index
            old_field = self._fields_map[f_name]
            try:
                idx = self._fields_list.index(old_field)
                # 2. Replace in list (preserve order)
                self._fields_list[idx] = field
            except ValueError:
                # Fallback safety if map/list synced incorrectly, append it
                self._fields_list.append(field)
            
            # 3. Update map
            self._fields_map[f_name] = field
        else:
            # Field doesn't exist, treat as add
            self.add_field(field)

    # -----------------------------------------------------------
    # Meta
    # -----------------------------------------------------------
    
    def clear_meta(self):
        self.clear_common_meta()
        self.required = False

    def apply_meta(self, info: MetaInfo):
        """
        Applies ALL metadata, including constraints (!required).
        """
        # 1. Apply common stuff (meta dict, comments)
        self.apply_common_meta(info)

        # 2. Apply Schema-specific constraints
        if info.required:
            self.required = True

    # -----------------------------------------------------------

    def encode(self, config: Config = {
        "indent": 2,
    }) -> str:
        """
        Debug fallback. Real encoder is in encoder.py.
        """
        from .Encoder import Encoder
        return Encoder(config).encode_schema(self)

    def __repr__(self):
        """
        Technical debug representation.
        Format: <Schema(KIND:type_name) name='...' details...>
        """
        # 1. Basic Info: Kind and TypeName
        kind_str = self.kind.name

        # Show type_name only if it is specific (e.g., 'User' or 'int'),
        # avoid redundancy if it is just 'any' or repeats the kind name.
        if self.type_name and self.type_name != "any" and self.type_name != self.kind.value:
            type_label = f":{self.type_name}"
        else:
            type_label = ""
            
        header = f"<Schema({kind_str}{type_label})"

        # 2. Field Name (if this schema represents a named field in a parent)
        name_str = f" name='{self.name}'" if self.name else ""

        # 3. Type-specific details (Concise summary)
        details = []

        # Meta: Attributes/Tags/Flags
        # We only show keys or presence to keep the log line short.
        if self.required:
            details.append("!required")
        if self.attr:
            details.append(f"attr={list(self.attr.keys())}") # Show keys only
        if self.tags:
            details.append(f"tags={self.tags}")
        if self.comments:
            details.append(f"comments={len(self.comments)}")
        

        # Structure: Record
        if self.is_record:
            # Instead of dumping all fields recursively, show count and first few names
            field_count = len(self._fields_list)
            if field_count > 0:
                # Show max 3 field names, truncate the rest
                field_names = [f.name for f in self._fields_list[:3]]
                if field_count > 3:
                    field_names.append("...")
                details.append(f"fields({field_count})=[{', '.join(field_names)}]")
            else:
                details.append("fields=[]")

        # Structure: List
        elif self.is_list:
            # Show element type summary without deep recursion
            el_type = self.element.type_name if self.element else "None"
            el_kind = self.element.kind.name if self.element else "ANY"
            details.append(f"element={el_kind}:{el_type}")

        # Assemble final string
        details_str = " " + " ".join(details) if details else ""
        
        return f"{header}{name_str}{details_str}>"