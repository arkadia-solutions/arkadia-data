use akd::{Answer, Format};
use arkadia_data as akd;
use serde_json::{json, Value};

#[test]
fn readme_example() {
    let data = json!({"users": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Alan"}]});
    let text = akd::encode(&data);
    assert_eq!(
        text,
        r#"<users:<[id:number,name:string]>>([(1,"Ada"),(2,"Alan")])"#
    );
    assert_eq!(akd::decode(&text).unwrap(), data);
    assert_eq!(
        akd::encode_pretty(&data),
        "< users:< [id:number, name:string ] > >\n([(1, \"Ada\"), (2, \"Alan\")])"
    );
}

#[test]
fn text_level_conversions() {
    let akd_text = akd::json_to_akd(r#"{"a":[1,2],"b":"x"}"#, true).unwrap();
    assert_eq!(akd_text, r#"<a:[number],b:string>([1,2],"x")"#);
    assert_eq!(
        akd::akd_to_json(&akd_text, false).unwrap(),
        r#"{"a":[1,2],"b":"x"}"#
    );
    assert_eq!(
        akd::convert(&akd_text, Format::Json).unwrap(),
        "{\n  \"a\": [\n    1,\n    2\n  ],\n  \"b\": \"x\"\n}"
    );
    assert_eq!(
        akd::convert(r#"{"a":1}"#, Format::AkDataCompact).unwrap(),
        "<a:number>(1)"
    );
    assert_eq!(akd::convert(r#"{"a":1}"#, Format::Toon).unwrap(), "a: 1");
}

#[test]
fn errors_are_reported() {
    assert!(matches!(
        akd::json_to_akd("{nope", true),
        Err(akd::Error::Json(_))
    ));
    match akd::decode("<a:number>(1") {
        Err(akd::Error::Decode(errors)) => assert!(errors[0].message.contains("not closed")),
        other => panic!("expected a decode error, got {other:?}"),
    }
    let lenient = akd::decode_lenient("<a:number>(1");
    assert_eq!(lenient.value, json!({"a": 1}));
    assert_eq!(lenient.errors.len(), 1);
}

#[test]
fn model_output_with_fences_and_metadata() {
    let text = "```\n/* top */ <result:<[name:string,total:number]>> $v=1 #t\n([(\"a\", 2), (\"b\", 3)])\n```";
    assert_eq!(
        akd::loads_any(text).unwrap(),
        json!({"result": [{"name": "a", "total": 2}, {"name": "b", "total": 3}]})
    );
    assert_eq!(
        akd::loads_any("```json\n{\"x\": 1}\n```").unwrap(),
        json!({"x": 1})
    );
}

#[test]
fn ansi_colours_are_ignored() {
    let data = json!({"a": [1, "x", null], "b": {"c": true}});
    let options = akd::EncodeOptions {
        colorize: true,
        ..akd::EncodeOptions::compact()
    };
    let coloured = akd::encode_with(&data, &options);
    assert!(coloured.contains('\x1b'));
    assert_eq!(akd::decode(&coloured).unwrap(), data);
}

#[test]
fn key_order_is_kept() {
    let data: Value = serde_json::from_str(r#"{"z":1,"a":2,"m":3}"#).unwrap();
    assert_eq!(akd::encode(&data), "<z:number,a:number,m:number>(1,2,3)");
}

#[test]
fn awkward_keys_round_trip() {
    for raw in [
        r#"{"`q`":1}"#,
        r#"{"":1,"0":2}"#,
        r#"[{"a b":1,"`":2},{"a b":3,"`":4}]"#,
        r#"{"x\ny":"\u0001"}"#,
    ] {
        let data: Value = serde_json::from_str(raw).unwrap();
        assert_eq!(akd::decode(&akd::encode(&data)).unwrap(), data, "{raw}");
        assert_eq!(
            akd::decode(&akd::encode_pretty(&data)).unwrap(),
            data,
            "{raw}"
        );
    }
}

/// Small deterministic generator (no dependencies).
struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }
    fn below(&mut self, n: u64) -> u64 {
        self.next() % n
    }
}

fn random_value(r: &mut Rng, depth: u32) -> Value {
    const KEYS: [&str; 9] = ["id", "name", "", "a b", "0", "`", "ü", "type", "k.v"];
    const STRS: [&str; 8] = ["", "x", "a,b", "q\"t", "b\\s", "l\nn", "null", "12"];
    let roll = r.below(100);
    if depth > 3 || roll < 35 {
        return match r.below(6) {
            0 => Value::Null,
            1 => Value::Bool(r.below(2) == 0),
            2 => json!(r.below(2000) as i64 - 1000),
            3 => json!((r.below(200000) as f64 - 100000.0) / 64.0),
            _ => json!(STRS[r.below(STRS.len() as u64) as usize]),
        };
    }
    if roll < 60 {
        let mut m = serde_json::Map::new();
        for _ in 0..r.below(5) {
            m.insert(
                KEYS[r.below(9) as usize].to_string(),
                random_value(r, depth + 1),
            );
        }
        return Value::Object(m);
    }
    if roll < 80 {
        let keys: Vec<&str> = (0..1 + r.below(3))
            .map(|_| KEYS[r.below(9) as usize])
            .collect();
        let rows = (0..r.below(6))
            .map(|_| {
                let mut m = serde_json::Map::new();
                for k in &keys {
                    if r.below(10) < 9 {
                        m.insert(k.to_string(), random_value(r, depth + 2));
                    }
                }
                Value::Object(m)
            })
            .collect();
        return Value::Array(rows);
    }
    Value::Array(
        (0..r.below(6))
            .map(|_| random_value(r, depth + 1))
            .collect(),
    )
}

#[test]
fn random_values_round_trip() {
    let mut r = Rng(0x9E3779B97F4A7C15);
    for i in 0..3000 {
        let data = random_value(&mut r, 0);
        let compact = akd::encode(&data);
        assert_eq!(
            akd::decode(&compact).unwrap_or_else(|e| panic!("#{i} {e:?}: {compact}")),
            data,
            "#{i} compact: {compact}"
        );
        let pretty = akd::encode_pretty(&data);
        assert_eq!(akd::decode(&pretty).unwrap(), data, "#{i} pretty: {pretty}");
    }
}

/// Every `examples/prompts/*/prompts.json` (written by Python), when the
/// repository is there.
fn example_prompts() -> Vec<Value> {
    let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/prompts");
    let mut files: Vec<_> = std::fs::read_dir(&dir)
        .map(|d| {
            d.filter_map(Result::ok)
                .map(|e| e.path().join("prompts.json"))
                .collect()
        })
        .unwrap_or_default();
    files.retain(|p: &std::path::PathBuf| p.exists());
    files.sort();
    files
        .iter()
        .map(|p| serde_json::from_str(&std::fs::read_to_string(p).unwrap()).unwrap())
        .collect()
}

const COMBOS: [(&str, bool, bool); 4] = [
    ("none", false, false),
    ("comments", true, false),
    ("attributes", false, true),
    ("both", true, true),
];

#[test]
fn prompts_match_the_bundled_examples() {
    let rows = example_prompts();
    let all = akd::examples::all();
    if rows.is_empty() {
        return; // packaged crate without the repository
    }
    assert_eq!(rows.len(), all.len());
    for (ex, row) in all.iter().zip(&rows) {
        for f in Format::PROMPT_FORMATS {
            for (combo, c, a) in COMBOS {
                let Some(expected) = row["prompts"][f.key()][combo].as_str() else {
                    continue;
                };
                assert_eq!(
                    ex.prompt_with(f, true, c, a),
                    expected,
                    "example {} {} {combo}",
                    ex.id,
                    f.label()
                );
            }
        }
    }
}

#[test]
fn token_estimate_matches_typescript() {
    // Sum over every example prompt, computed with the TypeScript estimateTokens.
    let rows = example_prompts();
    if rows.is_empty() {
        return;
    }
    let mut total = 0;
    for row in &rows {
        for k in ["json", "toon", "akd", "akcd"] {
            for (combo, _, _) in COMBOS {
                if let Some(t) = row["prompts"][k][combo].as_str() {
                    total += akd::estimate_tokens(t);
                }
            }
        }
    }
    assert_eq!(total, 450471);
}

#[test]
fn metadata_variants_decode_to_the_same_data() {
    for ex in akd::examples::all() {
        let Some(meta) = &ex.akd_meta else { continue };
        if ex.akd.is_none() {
            // hand-written feature examples keep their own form
            assert_eq!(
                akd::layout::strip_meta(meta, false, false),
                akd::encode(&ex.data),
                "example {}",
                ex.id
            );
        }
        for (_, c, a) in COMBOS {
            for f in [Format::AkData, Format::AkDataCompact] {
                assert_eq!(
                    akd::decode(&ex.data_text(f, c, a)).unwrap(),
                    ex.data,
                    "example {}",
                    ex.id
                );
            }
        }
    }
}

#[test]
fn formats_and_answers() {
    assert_eq!(
        "AK-DATA COMPACT".parse::<Format>().unwrap(),
        Format::AkDataCompact
    );
    assert_eq!("ak_data".parse::<Format>().unwrap(), Format::AkData);
    assert!("xml".parse::<Format>().is_err());
    let a = Answer::parse("name:string, total:number", None).unwrap();
    assert_eq!(
        a.instruction(Format::AkDataCompact).lines().last().unwrap(),
        "<result:<[name:string,total:number]>>"
    );
    let p = akd::build_prompt(&json!([{"a": 1}]), "Sum?", Format::Json, Some(&a), true);
    assert!(p.starts_with("The data below is in JSON.\n\n<data>\n"));
    assert!(p.ends_with("Answer with JSON only (no prose): {\"result\": [{\"name\": <string>, \"total\": <number>}, ...]}\n"));
}

#[test]
fn prompt_output_template() {
    let data = json!({"items": [{"sku": "a", "qty": 1}]});
    let options = akd::EncodeOptions {
        prompt_output: true,
        ..akd::EncodeOptions::pretty()
    };
    assert_eq!(
        akd::encode_with(&data, &options),
        "< items:< [sku:string, qty:number ] > >\n{\n  items: [\n    {\n      sku: string,\n      qty: number\n    },\n    ... /* repeat pattern for additional items */\n  ]\n}"
    );
}

#[test]
fn named_type_in_sibling_fields() {
    let text = "@Point<x:number,y:number> <start:@Point,end:@Point>((0,0),(3,4))";
    assert_eq!(
        akd::decode(text).unwrap(),
        json!({"start": {"x": 0, "y": 0}, "end": {"x": 3, "y": 4}})
    );
    let text = "@U<id:number> <a:@U,b:[@U],c:@U>((1),[(2),(3)],(4))";
    assert_eq!(
        akd::decode(text).unwrap(),
        json!({"a": {"id": 1}, "b": [{"id": 2}, {"id": 3}], "c": {"id": 4}})
    );
}

#[test]
fn layout_keeps_every_bundled_example() {
    for ex in akd::examples::all() {
        let compact = akd::encode(&ex.data);
        for width in [40, 80, 120] {
            let pretty = akd::layout::pretty(&compact, width);
            assert_eq!(
                akd::decode(&pretty).unwrap(),
                ex.data,
                "{} @{width}",
                ex.slug
            );
        }
    }
}

/// Lists of records with optional fields share one header; records are written
/// with only their first fields. Same cases as python/tests/test_20_lists.py.
#[test]
fn optional_fields_share_one_header() {
    let cases = [
        (
            json!({"items": [{"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 2}, {"a": 4, "b": 5, "c": 6, "d": 7}]}),
            "<items:<[a:number,b:number,c:number,d:number]>>([(1,2,3),(1,2),(4,5,6,7)])",
        ),
        (
            json!({"cust": [{"id": 7, "name": "Ada", "email": "a@x"}, {"id": 8, "name": "B"}, {"id": 9, "name": "C", "email": null}]}),
            r#"<cust:<[id:number,name:string,email:string]>>([(7,"Ada","a@x"),(8,"B"),(9,"C",null)])"#,
        ),
        (
            json!([{"name": "planner", "steps": 12}, {"name": "writer", "temp": 0.4}, {"name": "reviewer"}]),
            r#"<[name:string,steps:number,temp:number]>[("planner",12),<any> {name:"writer",temp:0.4},("reviewer")]"#,
        ),
        (
            json!({"a": [{"x": 1}, {"y": 2}]}),
            "<a:[any]>([{x:1},{y:2}])",
        ),
    ];
    for (data, expected) in cases {
        let text = akd::encode(&data);
        assert_eq!(text, expected);
        assert_eq!(akd::decode(&text).unwrap(), data);
    }
}

/// `$size=N` on lists (EncodeOptions::array_sizes).
#[test]
fn list_sizes() {
    let cases = [
        (
            json!({"t": [1, 2, 3], "u": [1], "rows": [{"id": 1, "tags": ["a", "b"]}, {"id": 2, "tags": []}]}),
            2,
            r#"<t:[number],u:[number],rows:<[id:number,tags:[string]]>>([//$size=3// 1,2,3],[1],[//$size=2// (1,[//$size=2// "a","b"]),(2,[])])"#,
        ),
        (
            json!([{"id": 1, "n": "x"}, {"id": 2}]),
            1,
            r#"<[id:number,n:string]>[//$size=2// (1,"x"),(2)]"#,
        ),
    ];
    for (data, min, expected) in cases {
        let options = akd::EncodeOptions {
            array_sizes: Some(min),
            ..akd::EncodeOptions::compact()
        };
        let text = akd::encode_with(&data, &options);
        assert_eq!(text, expected);
        assert_eq!(akd::decode(&text).unwrap(), data);
        let pretty = akd::EncodeOptions {
            array_sizes: Some(min),
            ..akd::EncodeOptions::pretty()
        };
        assert_eq!(
            akd::decode(&akd::encode_with(&data, &pretty)).unwrap(),
            data
        );
    }
}

#[test]
fn diff_merge_apply_history() {
    use akd::diff::{self, ChangeSet, Info};
    let old =
        json!({"users": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Alan"}], "debug": true});
    let new = json!({"users": [{"id": 2, "name": "Alan T."}, {"id": 3, "name": "Grace"}]});
    let changes = diff::diff(&old, &new);
    assert_eq!(diff::summary(&changes), (1, 2, 1));
    assert_eq!(changes[0].path, "users[id=2].name");
    assert_eq!(diff::apply(&old, &changes).unwrap(), new);
    assert_eq!(diff::apply(&new, &diff::reverse(&changes)).unwrap(), old);
    // Merge keeps what NEW does not mention.
    let merged = diff::merge(&old, &new);
    assert_eq!(merged["debug"], json!(true));
    assert_eq!(merged["users"].as_array().unwrap().len(), 3);
    // The history is an attribute: the data decodes unchanged.
    let info = Info {
        title: Some("Rename".into()),
        date: Some("2026-11-01T10:00:00Z".into()),
        ..Info::default()
    };
    let set = ChangeSet::new(changes, &info, None);
    let text = diff::with_history(&new, std::slice::from_ref(&set));
    assert!(
        text.contains(" // $changes=<[id:string,date:string,"),
        "{text}"
    );
    assert_eq!(akd::decode(&text).unwrap(), new);
    assert_eq!(diff::history(&text), vec![set]);
}

#[test]
fn shared_diff_fixtures() {
    // The same cases are checked by the Python and npm packages.
    use akd::diff::{self, ChangeSet, Info};
    let fixtures: Value = serde_json::from_str(include_str!("fixtures/diff.json")).unwrap();
    for case in fixtures["cases"].as_array().unwrap() {
        let (a, b) = (&case["a"], &case["b"]);
        let changes = diff::diff(a, b);
        assert_eq!(
            diff::changes_json(&changes),
            case["changes"],
            "{}",
            case["name"]
        );
        assert_eq!(diff::merge(a, b), case["merged"], "{}", case["name"]);
        assert_eq!(diff::apply(a, &changes).unwrap(), *b);
        assert_eq!(diff::apply(b, &diff::reverse(&changes)).unwrap(), *a);
        let info = Info {
            title: Some("t".into()),
            author: Some("Ada".into()),
            description: None,
            date: Some("2026-11-01T10:00:00Z".into()),
        };
        let set = ChangeSet::new(changes, &info, Some("0123456789"));
        assert_eq!(set.id, case["id"].as_str().unwrap(), "{}", case["name"]);
        assert_eq!(
            diff::with_history(b, &[set]),
            case["document"].as_str().unwrap()
        );
    }
}
