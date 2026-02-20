import arkadia as ak
from arkadia.data import Config, encode

# ==============================================================================
# 1. PROMPT OUTPUT TESTS (LLM-Friendly Blueprint Mode)
# ==============================================================================

CONFIG: Config = {
    "prompt_output": True,
    "compact": False,
    "include_schema": False,
    "colorize": False,
    "indent": 2,
}


def test_prompt_output_record_with_comments():
    """
    Validates that prompt_output=True transforms a record into a
    key-type-comment blueprint using { } braces instead of ( ) parentheses.
    """
    akd_text = """
    @User <
      id: number /* unique id */,
      name: string /* display name */
    >
    """

    result = ak.data.decode(akd_text)
    node = result.node
    assert not result.errors

    # We manually configure the encoder for this specific test
    output = encode(node, CONFIG).strip()

    expected = """{
  id: number /* unique id */,
  name: string /* display name */
}""".strip()
    assert output == expected


def test_prompt_output_list_template():
    """
    Validates that prompt_output=True shows only a single example element
    inside a list with a continuation comment (...).
    """
    akd_text = """
    <[ /* id */ id: number, name: string, val: <id: string, num: number> ]>
    [ (1, "n", ("id", 3)), (2), (3) ]
    """

    result = ak.data.decode(akd_text)
    node = result.node
    output = encode(node, CONFIG).strip()

    expected = """[
  {
    id: number /* id */,
    name: string,
    val: {
      id: string,
      num: number
    }
  },
  ... /* repeat pattern for additional items */
]""".strip()
    assert output == expected


def test_prompt_output_nested_record():
    """
    Verifies that nested structures also expand into blueprints in prompt mode.
    """
    akd_text = """
    <
      name: string,
      meta: < ver: number /* version number */ >
    >
    ("App", (1.0))
    """

    result = ak.data.decode(akd_text)
    node = result.node
    output = encode(node, CONFIG).strip()

    expected = """{
  name: string,
  meta: {
    ver: number /* version number */
  }
}""".strip()
    print(output)
    assert output == expected


def test_prompt_output_escaped_identifiers():
    """
    Ensures that escaped identifiers (backticks) are preserved in prompt mode.
    """
    akd_text = "< `User ID`: number /* system id */ > (123)"

    result = ak.data.decode(akd_text)
    node = result.node
    output = encode(node, CONFIG).strip()
    expected = """{
  `User ID`: number /* system id */
}""".strip()
    assert output == expected
