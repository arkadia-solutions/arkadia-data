=== AI DATA FORMAT BENCHMARK REPORT ===

Date:  2026-01-16 10:26:13
Model: gpt-4o-mini
System: Arkadia AI Data Formats

Starting performance benchmark on 11 files (Repeats: 50)...
...........

FILE                                JSON (tok/ms)      AICD (tok/ms)       AID (tok/ms)      TOON (tok/ms)  ΔTOK (AICD)
------------------------------------------------------------------------------------------
arrays-nested.json               675/ 0.0     567/ 0.2     643/ 0.2     841/ 0.2        -16.0%
arrays-objects.json             1023/ 0.0     822/ 0.4     937/ 0.4    1207/ 0.3        -19.6%
arrays-primitive.json            431/ 0.0     360/ 0.1     402/ 0.1     520/ 0.1        -16.5%
arrays-tabular.json              413/ 0.0     342/ 0.1     396/ 0.1     441/ 0.1        -17.2%
delimiters.json                 1292/ 0.0     970/ 0.5    1094/ 0.4    1498/ 0.4        -24.9%
normalization.json               527/ 0.0     409/ 0.1     466/ 0.1     625/ 0.1        -22.4%
objects.json                     833/ 0.0     580/ 0.4     645/ 0.2    1041/ 0.2        -30.4%
options.json                     423/ 0.0     335/ 0.1     381/ 0.1     482/ 0.1        -20.8%
primitives.json                 1015/ 0.0     732/ 0.3     844/ 0.4    1264/ 0.3        -27.9%
toon.json                        139/ 0.0     115/ 0.0     137/ 0.0     104/ 0.0        -17.3%
whitespace.json                  143/ 0.0     135/ 0.0     149/ 0.0     165/ 0.0         -5.6%
------------------------------------------------------------------------------------------
GLOBAL TOTALS:
JSON Tokens: 6914
TOON Tokens: 8188
AID Tokens:  6094
AICD Tokens: 5367 (-22.37% reduction)

CONCLUSION: AI.Compact format saved a total of 1547 tokens across the dataset.
Generation time impact: JSON total 0.12ms vs AICD 2.33ms
