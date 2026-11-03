"""Readable layout (same output as Rust `layout::pretty` and npm `pretty`)."""

import arkadia.data as akd
from arkadia.bench import prompts
from arkadia.data import layout

TEXT = '<users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])'


def test_pretty_and_compact():
    assert (
        layout.pretty(TEXT, 40)
        == '<users:<[id:number, name:string]>>\n([(1, "Ada"), (2, "Alan")])'
    )
    assert layout.pretty("<[number]>[1,2,3]") == "<[number]>\n[1, 2, 3]"
    assert layout.compact(layout.pretty(TEXT, 20)) == TEXT


def test_strip_meta_gives_the_encoder_text():
    for ex in prompts.load_examples():
        if ex.akd_meta and not ex.akd:  # hand-written feature examples keep their form
            assert layout.strip_meta(ex.akd_meta) == akd.encode(
                ex.data, {"compact": True}
            ), ex.slug
        if ex.akd_meta:
            assert akd.loads(layout.pretty(ex.akd_meta, 60)) == ex.data
