"""An unclosed // meta block with a digit in it used to loop forever."""

import pytest

import arkadia.data as akd


@pytest.mark.parametrize(
    "text",
    [
        "<a:number //>(1)",
        "<a:// 12 3 //number>(1)",
        "(1) // 9 //",
        "//",
        "<id:string,//",
    ],
)
def test_terminates(text):
    assert akd.decode(text).node is not None
