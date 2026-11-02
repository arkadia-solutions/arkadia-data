//! Same text as the Python package (fixtures written by
//! scripts/make_fixtures.py from `arkadia.data.dumps` and `toon_format`).

use arkadia_data as akd;
use serde_json::Value;

fn fixtures() -> Vec<Value> {
    serde_json::from_str(include_str!("fixtures.json")).expect("fixtures.json")
}

#[test]
fn compact_matches_python() {
    for case in fixtures() {
        let name = case["name"].as_str().unwrap();
        assert_eq!(
            akd::encode(&case["data"]),
            case["compact"].as_str().unwrap(),
            "{name}"
        );
    }
}

#[test]
fn pretty_matches_python() {
    for case in fixtures() {
        let name = case["name"].as_str().unwrap();
        assert_eq!(
            akd::encode_pretty(&case["data"]),
            case["pretty"].as_str().unwrap(),
            "{name}"
        );
    }
}

#[test]
fn toon_matches_reference() {
    for case in fixtures() {
        let name = case["name"].as_str().unwrap();
        assert_eq!(
            akd::toon::encode(&case["data"]),
            case["toon"].as_str().unwrap(),
            "{name}"
        );
    }
}

#[test]
fn python_text_decodes_to_the_data() {
    for case in fixtures() {
        let name = case["name"].as_str().unwrap();
        for key in ["compact", "pretty"] {
            let text = case[key].as_str().unwrap();
            assert_eq!(akd::decode(text).unwrap(), case["data"], "{name} [{key}]");
        }
    }
}
