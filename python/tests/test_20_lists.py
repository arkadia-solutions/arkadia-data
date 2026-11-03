"""
Lists of records with optional fields (one header for all of them, records
written with only their first fields) and list sizes ($size=N metadata).
The same cases are checked in typescript/tests/15.lists.test.ts and
rust/tests/api.rs.
"""

import arkadia.data as akd

CASES = [
    (
        {
            "items": [
                {"a": 1, "b": 2, "c": 3},
                {"a": 1, "b": 2},
                {"a": 4, "b": 5, "c": 6, "d": 7},
            ]
        },
        "<items:<[a:number,b:number,c:number,d:number]>>([(1,2,3),(1,2),(4,5,6,7)])",
    ),
    (
        {
            "cust": [
                {"id": 7, "name": "Ada", "email": "a@x"},
                {"id": 8, "name": "B"},
                {"id": 9, "name": "C", "email": None},
            ]
        },
        '<cust:<[id:number,name:string,email:string]>>([(7,"Ada","a@x"),(8,"B"),(9,"C",null)])',
    ),
    (
        [
            {"name": "planner", "steps": 12},
            {"name": "writer", "temp": 0.4},
            {"name": "reviewer"},
        ],
        '<[name:string,steps:number,temp:number]>[("planner",12),<any> {name:"writer",temp:0.4},("reviewer")]',
    ),
    ({"a": [{"x": 1}, {"y": 2}]}, "<a:[any]>([{x:1},{y:2}])"),
]

SIZES = [
    (
        {
            "t": [1, 2, 3],
            "u": [1],
            "rows": [{"id": 1, "tags": ["a", "b"]}, {"id": 2, "tags": []}],
        },
        2,
        '<t:[number],u:[number],rows:<[id:number,tags:[string]]>>([//$size=3// 1,2,3],[1],[//$size=2// (1,[//$size=2// "a","b"]),(2,[])])',
    ),
    (
        [{"id": 1, "n": "x"}, {"id": 2}],
        1,
        '<[id:number,n:string]>[//$size=2// (1,"x"),(2)]',
    ),
]


def test_optional_fields_share_one_header():
    for data, expected in CASES:
        text = akd.dumps(data)
        assert text == expected
        assert akd.loads(text) == data


def test_list_sizes():
    for data, minimum, expected in SIZES:
        text = akd.dumps(data, sizes=minimum)
        assert text == expected
        assert akd.loads(text) == data
        assert akd.loads(akd.dumps(data, indent=2, sizes=minimum)) == data
