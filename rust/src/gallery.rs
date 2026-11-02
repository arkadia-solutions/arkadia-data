//! The examples of `ak-data example`: the same catalogue as the website and
//! `ak-data prompt --example` (data/examples.json, written by
//! python/scripts/make_examples.py) — real-size examples and the feature
//! examples that each show one part of the format. Every example carries a
//! question with its expected answer, so it can be pasted into a chat model.

use serde_json::Value;

use crate::encoder::{encode, EncodeOptions};
use crate::prompt::{encode_as, Answer, Format, FORMAT_DEFINITION, TOON_DEFINITION};

/// One snippet of the gallery.
#[derive(Debug, Clone)]
pub struct Snippet {
    pub id: u64,
    pub slug: String,
    pub title: String,
    /// What this snippet shows about the format.
    pub shows: String,
    pub question: String,
    pub answer: Answer,
    pub expected: Value,
    /// The data as JSON.
    pub data: Value,
    /// Hand-written or annotated AK-DATA (comments, attributes, named types …),
    /// when the example has it.
    pub source: Option<String>,
    /// "feature", "metadata", "needs metadata".
    pub tags: Vec<String>,
}

impl Snippet {
    /// The snippet as AK-DATA text: the hand-written source, or the compact
    /// encoding of its data.
    pub fn akd(&self) -> String {
        match &self.source {
            Some(text) => text.clone(),
            None => encode(&self.data, &EncodeOptions::compact()),
        }
    }

    /// The data written in `format`; AK-DATA keeps a hand-written source
    /// (laid out to `width` for the readable form).
    pub fn text(&self, format: Format, width: usize) -> String {
        match format {
            Format::AkData => crate::layout::pretty(&self.akd(), width),
            Format::AkDataCompact => match &self.source {
                Some(text) => crate::layout::compact(text),
                None => encode_as(&self.data, Format::AkDataCompact),
            },
            other => encode_as(&self.data, other),
        }
    }

    /// The expected answer, as AK-DATA with the answer header.
    pub fn expected_akd(&self) -> String {
        let cols: Vec<String> = self
            .answer
            .fields
            .iter()
            .map(|(f, t)| format!("{}:{t}", crate::layout::name(f)))
            .collect();
        let rows: Vec<String> = self
            .expected
            .as_array()
            .map(|rows| {
                rows.iter()
                    .map(|row| {
                        // Missing trailing fields stay absent (fewer values).
                        let present = self
                            .answer
                            .fields
                            .iter()
                            .rposition(|(f, _)| row.get(f).is_some())
                            .map_or(0, |i| i + 1);
                        let values: Vec<String> = self.answer.fields[..present]
                            .iter()
                            .map(|(f, _)| {
                                let v = row.get(f).cloned().unwrap_or(Value::Null);
                                serde_json::to_string(&v).unwrap_or_default()
                            })
                            .collect();
                        format!("({})", values.join(","))
                    })
                    .collect()
            })
            .unwrap_or_default();
        format!(
            "<{}:<[{}]>>([{}])",
            self.answer.name,
            cols.join(","),
            rows.join(",")
        )
    }

    /// A copy-paste prompt: format definition, the data in `format`
    /// (readable AK-DATA laid out to `width`), the question and the answer
    /// header to fill.
    pub fn prompt(&self, format: Format, width: usize, definition: bool) -> String {
        let intro = match format {
            Format::AkData => "AK-DATA",
            Format::AkDataCompact => "AK-DATA (compact, single-line form)",
            other => other.label(),
        };
        let mut parts = vec![format!("The data below is in {intro}.")];
        if definition && format.is_ak_data() {
            parts.push(FORMAT_DEFINITION.to_string());
        } else if definition && format == Format::Toon {
            parts.push(TOON_DEFINITION.to_string());
        }
        parts.push(format!(
            "<data>\n{}\n</data>",
            self.text(format, width).trim_end()
        ));
        parts.push(format!("Question: {}", self.question));
        parts.push(self.answer.instruction(format));
        parts.join("\n\n") + "\n"
    }
}

/// Every example, by id.
pub fn all() -> Vec<Snippet> {
    crate::examples::all()
        .into_iter()
        .map(|e| Snippet {
            id: e.id,
            slug: e.slug,
            title: e.title,
            shows: e.description,
            question: e.question,
            answer: e.answer,
            expected: e.expected,
            data: e.data,
            source: e.akd_meta.or(e.akd),
            tags: e.tags,
        })
        .collect()
}

impl Snippet {
    /// True for the examples that show one part of the format.
    pub fn is_feature(&self) -> bool {
        self.tags.iter().any(|t| t == "feature")
    }
}

/// A snippet by id (`3`) or slug (`tool-result`).
pub fn get(key: &str) -> Option<Snippet> {
    all()
        .into_iter()
        .find(|s| s.id.to_string() == key || s.slug == key)
}

/// A pseudo-random snippet (`seed` decides which one).
pub fn pick(seed: u64) -> Snippet {
    let list = all();
    // splitmix64: neighbouring seeds give unrelated picks.
    let mut z = seed.wrapping_add(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^= z >> 31;
    list[(z % list.len() as u64) as usize].clone()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_snippet_round_trips_and_has_an_answer() {
        let list = all();
        assert!(list.len() >= 60);
        assert!(list.iter().filter(|s| s.is_feature()).count() >= 10);
        for s in &list {
            assert!(!s.data.is_null(), "{}", s.slug);
            for f in [Format::AkData, Format::AkDataCompact] {
                let back = crate::decode(&s.text(f, 60)).unwrap();
                assert_eq!(back, s.data, "{} {f}", s.slug);
            }
            let answer = crate::decode(&s.expected_akd()).unwrap();
            assert_eq!(answer[&s.answer.name], s.expected, "{}", s.slug);
            assert!(s.prompt(Format::AkData, 80, true).contains(&s.question));
        }
    }

    #[test]
    fn pick_covers_the_gallery() {
        let n = all().len();
        let seen: std::collections::HashSet<u64> = (0..2000).map(|s| pick(s).id).collect();
        assert_eq!(seen.len(), n);
    }
}
