"""A named type (@Name) reused by several fields of one header."""

import arkadia.data as akd


def test_named_type_in_sibling_fields():
    text = "@Point<x:number,y:number> <start:@Point,end:@Point>((0,0),(3,4))"
    assert akd.loads(text) == {"start": {"x": 0, "y": 0}, "end": {"x": 3, "y": 4}}


def test_named_type_in_fields_and_lists():
    text = "@U<id:number> <a:@U,b:[@U],c:@U>((1),[(2),(3)],(4))"
    assert akd.loads(text) == {
        "a": {"id": 1},
        "b": [{"id": 2}, {"id": 3}],
        "c": {"id": 4},
    }
