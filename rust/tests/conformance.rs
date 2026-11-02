#[test]
fn shared_semantic_corpus() {
    let corpus: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/conformance.json")).unwrap();
    for data in corpus["cases"].as_array().unwrap() {
        for text in [
            arkadia_data::encode(data),
            arkadia_data::encode_pretty(data),
        ] {
            assert_eq!(arkadia_data::decode(&text).unwrap(), *data, "{text}");
        }
    }
}
