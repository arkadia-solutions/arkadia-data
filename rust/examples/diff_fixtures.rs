//! Writes tests/fixtures/diff.json: diff / merge / change id / document of
//! each case, as computed here. The Python and npm packages check against it.
//!
//!   cargo run --example diff_fixtures > tests/fixtures/diff.json

use arkadia_data::diff::{self, ChangeSet, Info};
use serde_json::{json, Value};

fn main() {
    let cases = [
        ("same", json!({"a": 1}), json!({"a": 1})),
        (
            "scalar change",
            json!({"a": 1, "b": "x"}),
            json!({"a": 2, "b": "x"}),
        ),
        (
            "keys added and removed",
            json!({"a": 1, "gone": true}),
            json!({"a": 1, "new": [1, 2]}),
        ),
        (
            "nested record",
            json!({"cfg": {"cpu": 2, "mem": "4G"}}),
            json!({"cfg": {"cpu": 4, "mem": "4G", "disk": null}}),
        ),
        (
            "records by id",
            json!({"users": [{"id": 1, "name": "Ada", "tags": ["x"]}, {"id": 2, "name": "Alan", "tags": []}]}),
            json!({"users": [{"id": 1, "name": "Ada", "tags": ["x", "y"]}, {"id": 2, "name": "Alan T.", "tags": []}, {"id": 3, "name": "Grace", "tags": []}]}),
        ),
        (
            "records reordered",
            json!({"items": [{"sku": "a", "qty": 1}, {"sku": "b", "qty": 2}, {"sku": "c", "qty": 3}]}),
            json!({"items": [{"sku": "c", "qty": 3}, {"sku": "a", "qty": 5}, {"sku": "d", "qty": 1}]}),
        ),
        (
            "list by position",
            json!({"v": [1, 2, 3, 4]}),
            json!({"v": [1, 9]}),
        ),
        ("list grows", json!([1]), json!([1, 2, 3])),
        (
            "odd keys",
            json!({"a b": {"x.y": 1}, "9z": "zero"}),
            json!({"a b": {"x.y": 2}, "9z": "nil"}),
        ),
        ("type change", json!({"a": [1, 2]}), json!({"a": {"b": 1}})),
        (
            "records without key",
            json!({"r": [{"v": 1}, {"v": 1}]}),
            json!({"r": [{"v": 1}, {"v": 2}]}),
        ),
        (
            "first field as key",
            json!({"r": [{"name": "a", "n": 1}]}),
            json!({"r": [{"name": "a", "n": 2}, {"name": "b", "n": 0}]}),
        ),
        (
            "unicode",
            json!({"city": "Krakow"}),
            json!({"city": "Kraków", "note": "line\nbreak \"q\""}),
        ),
        ("root replaced", json!(1), json!("one")),
    ];
    let info = Info {
        title: Some("t".into()),
        author: Some("Ada".into()),
        description: None,
        date: Some("2026-11-01T10:00:00Z".into()),
    };
    let out: Vec<Value> = cases
        .iter()
        .map(|(name, a, b)| {
            let changes = diff::diff(a, b);
            let set = ChangeSet::new(changes.clone(), &info, Some("0123456789"));
            json!({
                "name": name,
                "a": a,
                "b": b,
                "changes": diff::changes_json(&changes),
                "merged": diff::merge(a, b),
                "id": set.id,
                "document": diff::with_history(b, &[set]),
            })
        })
        .collect();
    let doc = json!({
        "about": "diff / merge / apply cases shared by the Rust, Python and npm packages. Change id: parent 0123456789, date 2026-11-01T10:00:00Z, author Ada, title t. Regenerate: cargo run --example diff_fixtures",
        "cases": out,
    });
    println!("{}", serde_json::to_string_pretty(&doc).unwrap());
}
