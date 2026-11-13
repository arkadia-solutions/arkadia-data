# Metadata traps: 5 cases × 4 prompts

Used by `make check` (`python -m arkadia.bench.check`). Each case is one small table
whose numbers mean something a model cannot guess — a reversed sign, a unit, an error
code, a test record. Every case has four self-contained, copy-pasteable prompts:

| | Form | Metadata |
|---|---|---|
| A | JSON | none |
| B | JSON-meta | a `_meta` object with notes per field |
| C | AK-Data | none |
| D | AK-Data + comments | `/* … */` comments (on schema, fields, or single records) and `//$size=N//` |

**Expected** is the right answer; **trap answers** are what a model gives when it
relies on habits instead of the notes. Without metadata (A, C) the right answer is
mostly not reachable — that is the point: the check shows how much the notes help
and whether a model reads them in AK-Data as well as in JSON.

The script reads this file: keep the headings, the `Expected Answer` / `Trap Answers`
lines and the ```` ```text ```` blocks in this shape. Nullable fields in AK-Data are
written with the plain type (`replaces:number`, values may be `null`).

---

## 1. Accounting: Reversed Sign Convention & Currency Subunits

* **Expected Answer:** `250`
* **Trap Answers (without meta):** `-75000`, `-76000`, `-25000`, `-250`

**Prompt 1A — JSON:**

```text
Answer the question using only the data below. Reply with only the final number.

Data:
{
  "ledger": [
    {"tx_id": 101, "curr": "PLN", "debit_delta": 15000},
    {"tx_id": 102, "curr": "PLN", "debit_delta": -40000},
    {"tx_id": 901, "curr": "PLN", "debit_delta": -50000},
    {"tx_id": 103, "curr": "JPY", "debit_delta": -1000}
  ]
}

Question: What is the net cash change, in full PLN, from completed PLN transactions, excluding dry-run simulations?

```

**Prompt 1B — JSON-meta:**

```text
Answer the question using only the data below. Reply with only the final number.

Data:
{
  "_meta": {
    "debit_delta": "Positive = cash outflow (-cash), negative = cash inflow (+cash), so cash change = -debit_delta. PLN/EUR in minor units (1/100), JPY in 1:1.",
    "tx_id": "IDs >= 900 are dry-run simulations and must be excluded."
  },
  "ledger": [
    {"tx_id": 101, "curr": "PLN", "debit_delta": 15000},
    {"tx_id": 102, "curr": "PLN", "debit_delta": -40000},
    {"tx_id": 901, "curr": "PLN", "debit_delta": -50000},
    {"tx_id": 103, "curr": "JPY", "debit_delta": -1000}
  ]
}

Question: What is the net cash change, in full PLN, from completed PLN transactions, excluding dry-run simulations?

```

**Prompt 1C — AK-Data:**

```text
Answer the question using only the AK-Data below (header defines <field:type>, records follow positionally in parentheses). Reply with only the final number.

Data:
<ledger:<[tx_id:number,curr:string,debit_delta:number]>>([(101,"PLN",15000),(102,"PLN",-40000),(901,"PLN",-50000),(103,"JPY",-1000)])

Question: What is the net cash change, in full PLN, from completed PLN transactions, excluding dry-run simulations?

```

**Prompt 1D — AK-Data with comments meta:**

```text
Answer the question using only the AK-Data below (header defines <field:type>, records follow positionally in parentheses). Reply with only the final number.

Data:
/* tx_id>=900 is dry-run (ignore). debit_delta: + is outflow (-cash), - is inflow (+cash), so cash change = -debit_delta; PLN in grosze (1/100), JPY 1:1 */
<ledger:<[tx_id:number,curr:string,debit_delta:number]>>//$size=4//([(101,"PLN",15000),(102,"PLN",-40000),(901,"PLN",-50000),(103,"JPY",-1000)])

Question: What is the net cash change, in full PLN, from completed PLN transactions, excluding dry-run simulations?

```

---

## 2. IoT Telemetry: In-Band Error Codes & Mode Multipliers

* **Expected Answer:** `140` (or `140.0`)
* **Trap Answers (without meta):** `999.9`, `650`, `650.0`

**Prompt 2A — JSON:**

```text
Answer the question using only the data below. Reply with only the final number.

Data:
{
  "sensors": [
    {"id": "S1", "mode": 1, "pressure": 120.5},
    {"id": "S2", "mode": 1, "pressure": 999.9},
    {"id": "S3", "mode": 2, "pressure": 650.0},
    {"id": "S4", "mode": 2, "pressure": 140.0}
  ]
}

Question: What was the highest actual pressure (in bars) recorded by a functioning sensor?

```

**Prompt 2B — JSON-meta:**

```text
Answer the question using only the data below. Reply with only the final number.

Data:
{
  "_meta": {
    "pressure": "999.9 indicates sensor fault (ignore). Mode 1 is in bars; in mode 2, readings > 500 are in decibars (divide by 10 for bars, otherwise already in bars)."
  },
  "sensors": [
    {"id": "S1", "mode": 1, "pressure": 120.5},
    {"id": "S2", "mode": 1, "pressure": 999.9},
    {"id": "S3", "mode": 2, "pressure": 650.0},
    {"id": "S4", "mode": 2, "pressure": 140.0}
  ]
}

Question: What was the highest actual pressure (in bars) recorded by a functioning sensor?

```

**Prompt 2C — AK-Data:**

```text
Answer the question using only the AK-Data below (header defines <field:type>, records follow positionally in parentheses). Reply with only the final number.

Data:
<sensors:<[id:string,mode:number,pressure:number]>>([("S1",1,120.5),("S2",1,999.9),("S3",2,650.0),("S4",2,140.0)])

Question: What was the highest actual pressure (in bars) recorded by a functioning sensor?

```

**Prompt 2D — AK-Data with comments meta:**

```text
Answer the question using only the AK-Data below (header defines <field:type>, records follow positionally in parentheses). Reply with only the final number.

Data:
/* pressure: 999.9 = sensor error (ignore); mode 1 is bars; in mode 2, readings > 500 are decibars (divide by 10 for bars, <= 500 is bars) */
<sensors:<[id:string,mode:number,pressure:number]>>//$size=4//([("S1",1,120.5),("S2",1,999.9),("S3",2,650.0),("S4",2,140.0)])

Question: What was the highest actual pressure (in bars) recorded by a functioning sensor?

```

---

## 3. Security (IAM): Protection Rings & Suspension Bitmasks

* **Expected Answer:** `charlie`
* **Trap Answers (without meta):** `alice`, `bob`

**Prompt 3A — JSON:**

```text
Answer the question using only the data below. Reply with only the username.

Data:
{
  "iam": [
    {"user": "alice", "role_level": 5, "deny_mask": 0},
    {"user": "bob", "role_level": 0, "deny_mask": 4},
    {"user": "charlie", "role_level": 0, "deny_mask": 0},
    {"user": "dave", "role_level": 1, "deny_mask": 0}
  ]
}

Question: Which user currently holds active highest-level privileges in the system?

```

**Prompt 3B — JSON-meta:**

```text
Answer the question using only the data below. Reply with only the username.

Data:
{
  "_meta": {
    "role_level": "Ring security convention: 0 = highest privilege (root), 5 = lowest (guest).",
    "deny_mask": "Bitmask of active blocks. Any value > 0 suspends the account completely."
  },
  "iam": [
    {"user": "alice", "role_level": 5, "deny_mask": 0},
    {"user": "bob", "role_level": 0, "deny_mask": 4},
    {"user": "charlie", "role_level": 0, "deny_mask": 0},
    {"user": "dave", "role_level": 1, "deny_mask": 0}
  ]
}

Question: Which user currently holds active highest-level privileges in the system?

```

**Prompt 3C — AK-Data:**

```text
Answer the question using only the AK-Data below (header defines <field:type>, records follow positionally in parentheses). Reply with only the username.

Data:
<iam:<[user:string,role_level:number,deny_mask:number]>>([("alice",5,0),("bob",0,4),("charlie",0,0),("dave",1,0)])

Question: Which user currently holds active highest-level privileges in the system?

```

**Prompt 3D — AK-Data with comments meta:**

```text
Answer the question using only the AK-Data below (header defines <field:type>, records follow positionally in parentheses). Reply with only the username.

Data:
/* role_level: 0 is highest (root), 5 is lowest. deny_mask > 0 means account is suspended */
<iam:<[user:string,role_level:number,deny_mask:number]>>//$size=4//([("alice",5,0),("bob",0,4),("charlie",0,0),("dave",1,0)])

Question: Which user currently holds active highest-level privileges in the system?

```

---

## 4. E-Commerce Orders: Status Codes, Subunits & Single-Record Comment

* **Expected Answer:** `53.99`
* **Trap Answers (without meta):** `105399`, `1053.99`, `5399`, `109049`, `1090.49`, `9049`, `90.49`

**Prompt 4A — JSON:**

```text
Answer the question using only the data below. Reply with only the final number.

Data:
{
  "orders": [
    {"id": 101, "st": 2, "amount": 1250},
    {"id": 102, "st": 4, "amount": 899},
    {"id": 103, "st": 3, "amount": 2400},
    {"id": 104, "st": 4, "amount": 4500},
    {"id": 999, "st": 4, "amount": 100000}
  ]
}

Question: What is the total refunded amount (in EUR) across real orders?

```

**Prompt 4B — JSON-meta:**

```text
Answer the question using only the data below. Reply with only the final number.

Data:
{
  "_meta": {
    "orders": {
      "size": 5,
      "fields": {
        "st": "1 new, 2 paid, 3 shipped, 4 refunded",
        "amount": "EUR cents"
      },
      "test_records": [999]
    }
  },
  "orders": [
    {"id": 101, "st": 2, "amount": 1250},
    {"id": 102, "st": 4, "amount": 899},
    {"id": 103, "st": 3, "amount": 2400},
    {"id": 104, "st": 4, "amount": 4500},
    {"id": 999, "st": 4, "amount": 100000}
  ]
}

Question: What is the total refunded amount (in EUR) across real orders?

```

**Prompt 4C — AK-Data:**

```text
Answer the question using only the AK-Data below (header defines <field:type>, records follow positionally in parentheses). Reply with only the final number.

Data:
<orders:<[
id:number,
st:number,
amount:number ]>>
[
  (101,2,1250),
  (102,4,899),
  (103,3,2400),
  (104,4,4500),
  (999,4,100000)
]

Question: What is the total refunded amount (in EUR) across real orders?

```

**Prompt 4D — AK-Data with comments meta:**

```text
Answer the question using only the AK-Data below (header defines <field:type>, records follow positionally in parentheses). Reply with only the final number.

Data:
<orders:<[
id:number,
st:number /* 1=new, 2=paid, 3=shipped, 4=refunded */,
amount:number /* EUR cents */ ]>>
//$size=5//
[
  (101,2,1250),
  (102,4,899),
  (103,3,2400),
  (104,4,4500),
  /* test record */
  (999,4,100000)
]

Question: What is the total refunded amount (in EUR) across real orders?

```

---

## 5. HR Systems: Mid-Stream Grading Scale Recalibration

* **Expected Answer:** `E1, E5`
* **Trap Answers (without meta):** `E1, E3`, `E1, E4, E5`

**Prompt 5A — JSON:**

```text
Answer the question using only the data below. Reply with only a comma-separated list of employee IDs.

Data:
{
  "reviews": [
    {"emp": "E1", "yr": 2025, "contract": "PERM", "grade": 5},
    {"emp": "E2", "yr": 2025, "contract": "PERM", "grade": 1},
    {"emp": "E3", "yr": 2026, "contract": "PERM", "grade": 5},
    {"emp": "E4", "yr": 2026, "contract": "EXT", "grade": 1},
    {"emp": "E5", "yr": 2026, "contract": "PERM", "grade": 1}
  ]
}

Question: Which bonus-eligible employees achieved the top performance grade in their respective review year?

```

**Prompt 5B — JSON-meta:**

```text
Answer the question using only the data below. Reply with only a comma-separated list of employee IDs.

Data:
{
  "_meta": {
    "grade": "In 2025: 1-5 scale (5 = best). In 2026: German 1-6 scale (1 = best, 5 = poor).",
    "contract": "EXT contractors are excluded from the bonus pool."
  },
  "reviews": [
    {"emp": "E1", "yr": 2025, "contract": "PERM", "grade": 5},
    {"emp": "E2", "yr": 2025, "contract": "PERM", "grade": 1},
    {"emp": "E3", "yr": 2026, "contract": "PERM", "grade": 5},
    {"emp": "E4", "yr": 2026, "contract": "EXT", "grade": 1},
    {"emp": "E5", "yr": 2026, "contract": "PERM", "grade": 1}
  ]
}

Question: Which bonus-eligible employees achieved the top performance grade in their respective review year?

```

**Prompt 5C — AK-Data:**

```text
Answer the question using only the AK-Data below (header defines <field:type>, records follow positionally in parentheses). Reply with only a comma-separated list of employee IDs.

Data:
<reviews:<[emp:string,yr:number,contract:string,grade:number]>>([("E1",2025,"PERM",5),("E2",2025,"PERM",1),("E3",2026,"PERM",5),("E4",2026,"EXT",1),("E5",2026,"PERM",1)])

Question: Which bonus-eligible employees achieved the top performance grade in their respective review year?

```

**Prompt 5D — AK-Data with comments meta:**

```text
Answer the question using only the AK-Data below (header defines <field:type>, records follow positionally in parentheses). Reply with only a comma-separated list of employee IDs.

Data:
/* grade: in 2025 5=best; in 2026 1=best (reversed scale). contract="EXT" is excluded from bonus */
<reviews:<[emp:string,yr:number,contract:string,grade:number]>>//$size=5//([("E1",2025,"PERM",5),("E2",2025,"PERM",1),("E3",2026,"PERM",5),("E4",2026,"EXT",1),("E5",2026,"PERM",1)])

Question: Which bonus-eligible employees achieved the top performance grade in their respective review year?

```
