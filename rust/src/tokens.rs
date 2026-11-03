//! Token estimate without a tokenizer (same rules as the Python and
//! TypeScript packages, mean error ~5% against o200k_base): a word with its
//! leading space is one token plus one per 7 further letters, digits come in
//! groups of three, punctuation runs cost one token per 4 characters, each
//! whitespace run one token.

fn is_letter(c: char) -> bool {
    c.is_alphabetic()
}

fn is_digit(c: char) -> bool {
    c.is_numeric()
}

fn is_punct(c: char) -> bool {
    !c.is_whitespace() && !is_letter(c) && !is_digit(c) && c != '_'
}

/// Estimated number of tokens of `text`.
pub fn estimate_tokens(text: &str) -> usize {
    let chars: Vec<char> = text.chars().collect();
    let n = chars.len();
    let mut i = 0;
    let mut total = 0;
    while i < n {
        let c = chars[i];
        let next = chars.get(i + 1).copied();
        let space = c == ' ';
        // A piece may start with one space followed by its own class.
        let start = if space && next.is_some_and(|x| is_letter(x) || is_digit(x) || is_punct(x)) {
            i + 1
        } else {
            i
        };
        let head = chars[start];
        if is_letter(head) {
            let mut j = start;
            while j < n && is_letter(chars[j]) {
                j += 1;
            }
            total += 1 + (j - start - 1) / 7;
            i = j;
        } else if is_digit(head) {
            let mut j = start;
            while j < n && j - start < 3 && is_digit(chars[j]) {
                j += 1;
            }
            total += 1;
            i = j;
        } else if is_punct(head) {
            let mut j = start;
            while j < n && is_punct(chars[j]) {
                j += 1;
            }
            while j < n && (chars[j] == '\r' || chars[j] == '\n') {
                j += 1;
            }
            total += (j - start).div_ceil(4);
            i = j;
        } else if head.is_whitespace() {
            let mut j = i;
            while j < n && chars[j].is_whitespace() {
                j += 1;
            }
            total += 1;
            i = j;
        } else {
            // "_" and other unmatched characters cost nothing (as the regex).
            i += 1;
        }
    }
    total
}

#[cfg(test)]
mod tests {
    use super::estimate_tokens;

    #[test]
    fn small_cases() {
        // Reference values from the TypeScript estimateTokens.
        assert_eq!(estimate_tokens(""), 0);
        assert_eq!(estimate_tokens("hello world"), 2);
        assert_eq!(estimate_tokens("12345"), 2);
        assert_eq!(estimate_tokens("{\"a\":1}"), 5);
        assert_eq!(estimate_tokens("  x_y  \n\n"), 4);
        assert_eq!(estimate_tokens("żółw 🐢 abcdefghij"), 4);
        assert_eq!(estimate_tokens("<a:number>(1)"), 7);
    }
}
