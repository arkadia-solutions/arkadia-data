from typing import Optional, List, Dict, Union, Any
from enum import Enum


class MetaInfo:
    """
    A temporary container (DTO) holding parsed metadata from a / ... / block.
    It contains BOTH Schema constraints (!required) and Node attributes ($key=val).
    """
    def __init__(self):
        # Common (Node & Schema)
        self.attr: Dict[str, Any] = {}        # $key=value
        self.comments: List[str] = []         # /* comments */
        self.tags: List[str] = []             # #["tag1"]

        # Schema Only (Constraints)
        self.required: bool = False           # !required

    def apply_meta(self, info: "MetaInfo"):
        # Append comments
        if info.comments:
            self.comments.extend(info.comments)

        # Merge attributes ($key=value)
        if info.attr:
            self.attr.update(info.attr)
            
        # Append tags
        if info.tags:
            self.tags.extend(info.tags)

        # Override required meta
        self.required = info.required

    def __bool__(self):
        """
        Allows usage: 'if meta:' to check if any metadata was collected.
        Returns False if the container is effectively empty.
        """
        return bool(self.attr or self.tags or self.comments or self.required)
    

    def __repr__(self):
        """
        Debug representation mimicking the actual ADF format style.
        Example: <MetaInfo !required #tag $key=val /* 2 comments */>
        """
        parts = []

        # 1. Flags
        if self.required:
            parts.append("!required")

        # 2. Tags
        for t in self.tags:
            parts.append(f"#{t}")

        # 3. Attributes
        for k, v in self.attr.items():
            # Simplistic value repr
            val_str = str(v).lower() if isinstance(v, bool) else repr(v)
            parts.append(f"${k}={val_str}")

        # 4. Comments (Summary)
        if self.comments:
            if len(self.comments) == 1:
                # Show short comment content if singular
                c = self.comments[0]
                preview = (c[:15] + '..') if len(c) > 15 else c
                parts.append(f"/* {preview} */")
            else:
                parts.append(f"/* {len(self.comments)} comments */")

        content = " ".join(parts)
        return f"<MetaInfo {content}>" if content else "<MetaInfo (empty)>"

class Meta:
    """
    Mixin class that adds metadata storage capabilities to Node and Schema.
    """
    def __init__(self, 
                 comments: Optional[List[str]] = None,
                 attr: Optional[Dict[str, Any]] = None, 
                 tags: Optional[List[str]] = None):
        self.comments = comments if comments is not None else []
        self.attr = attr if attr is not None else {}
        self.tags = tags if tags is not None else []

    
    def clear_common_meta(self):
        """
        Clears ALL metadata,
        """
        self.comments = []
        self.attr = {}
        self.tags = []


    def apply_common_meta(self, info: 'MetaInfo'):
        """
        Merges only the common fields (attributes, comments, tags) 
        from a MetaInfo object. Safe for both Node and Schema.
        """

        # Append comments
        if info.comments:
            self.comments.extend(info.comments)

        # Merge attributes ($key=value)
        if info.attr:
            self.attr.update(info.attr)
            
        # Append tags
        if info.tags:
            self.tags.extend(info.tags)