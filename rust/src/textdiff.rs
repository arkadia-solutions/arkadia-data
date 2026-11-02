//! Line diff (Myers) and unified hunks for `ak-data diff`.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Same,
    Del,
    Ins,
}

#[derive(Debug, Clone, Copy)]
pub struct Line<'a> {
    pub kind: Kind,
    pub text: &'a str,
    /// 1-based line numbers in the old / new text.
    pub old_no: usize,
    pub new_no: usize,
}

/// Edit distance above which the middle part is shown as replaced as a whole.
const MAX_D: usize = 2000;

/// The lines of `a` and `b` as kept / deleted / inserted.
pub fn lines<'a>(a: &[&'a str], b: &[&'a str]) -> Vec<Line<'a>> {
    let pre = a.iter().zip(b).take_while(|(x, y)| x == y).count();
    let suf = a[pre..]
        .iter()
        .rev()
        .zip(b[pre..].iter().rev())
        .take_while(|(x, y)| x == y)
        .count();
    let (ma, mb) = (&a[pre..a.len() - suf], &b[pre..b.len() - suf]);
    let mut kinds: Vec<(Kind, &'a str)> = a[..pre].iter().map(|t| (Kind::Same, *t)).collect();
    kinds.extend(myers(ma, mb));
    kinds.extend(a[a.len() - suf..].iter().map(|t| (Kind::Same, *t)));
    let (mut o, mut n) = (0, 0);
    kinds
        .into_iter()
        .map(|(kind, text)| {
            match kind {
                Kind::Same => {
                    o += 1;
                    n += 1;
                }
                Kind::Del => o += 1,
                Kind::Ins => n += 1,
            }
            Line {
                kind,
                text,
                old_no: o,
                new_no: n,
            }
        })
        .collect()
}

fn myers<'a>(a: &[&'a str], b: &[&'a str]) -> Vec<(Kind, &'a str)> {
    let (n, m) = (a.len() as isize, b.len() as isize);
    let whole = || {
        let mut out: Vec<(Kind, &'a str)> = a.iter().map(|t| (Kind::Del, *t)).collect();
        out.extend(b.iter().map(|t| (Kind::Ins, *t)));
        out
    };
    if n == 0 || m == 0 {
        return whole();
    }
    let max = (n + m) as usize;
    let off = max as isize;
    let mut v = vec![0isize; 2 * max + 2];
    // trace[d]: v[-d..=d] before step d.
    let mut trace: Vec<Vec<isize>> = Vec::new();
    let mut end = None;
    'outer: for d in 0..=max.min(MAX_D) as isize {
        trace.push(v[(off - d) as usize..=(off + d) as usize].to_vec());
        let mut k = -d;
        while k <= d {
            let i = (off + k) as usize;
            let mut x = if k == -d || (k != d && v[i - 1] < v[i + 1]) {
                v[i + 1]
            } else {
                v[i - 1] + 1
            };
            let mut y = x - k;
            while x < n && y < m && a[x as usize] == b[y as usize] {
                x += 1;
                y += 1;
            }
            v[i] = x;
            if x >= n && y >= m {
                end = Some(d);
                break 'outer;
            }
            k += 2;
        }
    }
    let Some(dmax) = end else { return whole() };
    let mut out = Vec::new();
    let (mut x, mut y) = (n, m);
    for d in (1..=dmax).rev() {
        let t = &trace[d as usize];
        let at = |k: isize| t[(k + d) as usize];
        let k = x - y;
        let prev_k = if k == -d || (k != d && at(k - 1) < at(k + 1)) {
            k + 1
        } else {
            k - 1
        };
        let px = at(prev_k);
        let py = px - prev_k;
        while x > px && y > py {
            x -= 1;
            y -= 1;
            out.push((Kind::Same, a[x as usize]));
        }
        if prev_k == k + 1 {
            y -= 1;
            out.push((Kind::Ins, b[y as usize]));
        } else {
            x -= 1;
            out.push((Kind::Del, a[x as usize]));
        }
    }
    while x > 0 && y > 0 {
        x -= 1;
        y -= 1;
        out.push((Kind::Same, a[x as usize]));
    }
    out.reverse();
    out
}

/// Ranges of `lines` to show: every change with `context` lines around it,
/// overlapping ranges joined.
pub fn hunks(lines: &[Line], context: usize) -> Vec<std::ops::Range<usize>> {
    let mut out: Vec<std::ops::Range<usize>> = Vec::new();
    for (i, l) in lines.iter().enumerate() {
        if l.kind == Kind::Same {
            continue;
        }
        let start = i.saturating_sub(context);
        let end = (i + context + 1).min(lines.len());
        match out.last_mut() {
            Some(last) if start <= last.end => last.end = last.end.max(end),
            _ => out.push(start..end),
        }
    }
    out
}

/// Common prefix and suffix (in chars) of two lines, for highlighting the
/// part that changed.
pub fn changed_span(a: &str, b: &str) -> (usize, usize) {
    let (ca, cb): (Vec<char>, Vec<char>) = (a.chars().collect(), b.chars().collect());
    let pre = ca.iter().zip(&cb).take_while(|(x, y)| x == y).count();
    let max_suf = ca.len().min(cb.len()) - pre;
    let suf = ca
        .iter()
        .rev()
        .zip(cb.iter().rev())
        .take(max_suf)
        .take_while(|(x, y)| x == y)
        .count();
    (pre, suf)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn kinds(a: &str, b: &str) -> String {
        let (la, lb): (Vec<&str>, Vec<&str>) = (a.split(' ').collect(), b.split(' ').collect());
        lines(&la, &lb)
            .iter()
            .map(|l| match l.kind {
                Kind::Same => format!(" {}", l.text),
                Kind::Del => format!("-{}", l.text),
                Kind::Ins => format!("+{}", l.text),
            })
            .collect::<Vec<_>>()
            .join(" ")
    }

    #[test]
    fn minimal_edits() {
        assert_eq!(kinds("a b c d", "a x c d"), " a -b +x  c  d");
        assert_eq!(kinds("a b c", "a b c d e"), " a  b  c +d +e");
        assert_eq!(kinds("x a b", "a b"), "-x  a  b");
        assert_eq!(kinds("a b c d e f", "a c d f g"), " a -b  c  d -e  f +g");
    }

    #[test]
    fn hunks_join_close_changes() {
        let a: Vec<String> = (0..30).map(|i| i.to_string()).collect();
        let mut b = a.clone();
        b[5] = "x".into();
        b[8] = "y".into();
        b[25] = "z".into();
        let (ra, rb): (Vec<&str>, Vec<&str>) = (
            a.iter().map(String::as_str).collect(),
            b.iter().map(String::as_str).collect(),
        );
        let l = lines(&ra, &rb);
        assert_eq!(hunks(&l, 3).len(), 2);
        assert_eq!(changed_span("users: Alan,", "users: Alan T.,"), (11, 1));
    }
}
