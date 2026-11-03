# Copy-paste prompt examples

66 prompts with data, a question and the expected answer, in JSON, TOON,
AK-DATA and AK-DATA COMPACT. Paste one into ChatGPT, Gemini, Claude or any chat
model and compare the answers and the token counts. Every AK-DATA prompt contains
the format definition, so no setup is needed.

48 examples carry **metadata** — the same facts as `$attributes`/`#tags` and as
`/* comments */` (for JSON and TOON: notes before the data). Each prompt can be
built with attributes, with comments, with both or without:
`ak-data prompt --example 11 --attributes --comments`. In
25 of them the question can only be answered with the metadata (*needs
metadata*): what a code means, a unit, which records are tests.

Each folder has the prompt in every format (`json.txt`, `toon.txt`, `ak-data.txt`,
`ak-data-compact.txt`; with attributes and comments: `*.meta.txt`), the expected
answer and `prompts.json` with every combination. Regenerate with `make examples`.

Prompt tokens (o200k_base, format definition included):

| # | example | tags | JSON | TOON | AK-DATA | AK-DATA COMPACT | AK-DATA COMPACT + metadata |
|---|---|---|---:|---:|---:|---:|---:|
| 1 | [HR table: average salary by department](01-employees-salaries/) | metadata | 2,359 | 1,147 | 1,497 | 1,221 | 1,272 |
| 2 | [E-commerce: revenue per country (nested orders)](02-orders-revenue/) |  | 2,968 | 1,691 | 1,739 | 1,309 | – |
| 3 | [Ops: which service is failing? (logs)](03-logs-incidents/) | metadata | 3,779 | 1,820 | 2,216 | 1,853 | 1,884 |
| 4 | [Agent tool result: pick the best search hits](04-search-tool-result/) | metadata | 1,394 | 988 | 1,311 | 1,083 | 1,106 |
| 5 | [Analytics: best days in a time series](05-analytics-top-days/) | metadata | 1,600 | 808 | 1,025 | 875 | 893 |
| 6 | [Developer data: filter repositories](06-repositories-filter/) |  | 2,234 | 1,672 | 1,281 | 1,078 | – |
| 7 | [Support: unassigned urgent tickets](07-support-triage/) |  | 1,754 | 843 | 1,156 | 964 | – |
| 8 | [Inventory: what to reorder and how much](08-inventory-reorder/) | metadata | 1,655 | 705 | 984 | 808 | 830 |
| 9 | [Scheduling: find a common free hour](09-calendar-free-slots/) | metadata | 1,299 | 614 | 845 | 704 | 723 |
| 10 | [Extraction: emails to structured orders (output format)](10-email-extraction/) |  | 349 | 352 | 473 | 445 | – |
| 11 | [Invoices: overdue and unpaid](11-invoices-overdue/) | metadata, needs metadata | 793 | 486 | 643 | 578 | 681 |
| 12 | [Departures: delayed flights](12-flights-delays/) | metadata | 642 | 351 | 507 | 447 | 497 |
| 13 | [School grades: average per class](13-grades-classes/) | metadata | 633 | 325 | 483 | 417 | 478 |
| 14 | [Crypto prices: top movers](14-crypto-movers/) | metadata, needs metadata | 355 | 256 | 371 | 345 | 403 |
| 15 | [Weather: Fahrenheit forecast](15-forecast-fahrenheit/) | metadata, needs metadata | 300 | 224 | 336 | 313 | 367 |
| 16 | [Bank account: spending per category](16-bank-spending/) | metadata, needs metadata | 626 | 402 | 522 | 473 | 527 |
| 17 | [Servers: CPU above 80 %](17-servers-cpu/) | metadata, needs metadata | 550 | 308 | 453 | 402 | 459 |
| 18 | [Web vitals: slow pages](18-web-vitals/) | metadata | 427 | 279 | 406 | 359 | 426 |
| 19 | [CRM: leads in the proposal stage](19-crm-leads/) | metadata, needs metadata | 697 | 363 | 530 | 455 | 506 |
| 20 | [Shipments: weight per carrier](20-shipments-weight/) | metadata, needs metadata | 522 | 311 | 448 | 404 | 415 |
| 21 | [Recipes: nut-free and quick](21-recipes-nut-free/) | metadata | 381 | 334 | 396 | 369 | 387 |
| 22 | [Films: best-rated drama](22-movies-best-drama/) | metadata | 628 | 530 | 507 | 465 | 487 |
| 23 | [Git log: most active authors](23-git-commits/) | metadata | 828 | 465 | 617 | 542 | 564 |
| 24 | [Hotel: revenue per room type](24-hotel-revenue/) | metadata | 545 | 285 | 433 | 382 | 400 |
| 25 | [HR: approved leave per person](25-hr-leave/) | metadata, needs metadata | 578 | 303 | 462 | 408 | 442 |
| 26 | [IoT tags: low battery](26-iot-batteries/) | metadata, needs metadata | 589 | 324 | 465 | 413 | 441 |
| 27 | [API: slow endpoints](27-api-latency/) | metadata, needs metadata | 376 | 269 | 382 | 356 | 386 |
| 28 | [Menu: vegan dishes under 25 PLN](28-menu-vegan/) | metadata, needs metadata | 332 | 319 | 355 | 343 | 390 |
| 29 | [Library: overdue loans](29-library-overdue/) |  | 393 | 293 | 409 | 385 | – |
| 30 | [Company cars: service due](30-fleet-service/) | metadata | 566 | 341 | 474 | 430 | 452 |
| 31 | [Shopping cart: total after discounts](31-cart-total/) | metadata, needs metadata | 220 | 208 | 320 | 298 | 329 |
| 32 | [Survey: share of agreement](32-survey-agree/) | metadata, needs metadata | 414 | 340 | 448 | 389 | 433 |
| 33 | [Football: most goals scored](33-football-goals/) | metadata | 499 | 431 | 426 | 384 | 394 |
| 34 | [Energy meter: kWh per day](34-energy-kwh/) | metadata, needs metadata | 554 | 364 | 479 | 436 | 475 |
| 35 | [Job board: remote and well paid](35-jobs-remote/) | metadata | 500 | 300 | 442 | 406 | 445 |
| 36 | [GitHub: open bugs](36-github-bugs/) |  | 648 | 542 | 476 | 422 | – |
| 37 | [Support: SLA breaches](37-support-sla/) | metadata, needs metadata | 528 | 291 | 440 | 396 | 458 |
| 38 | [Exchange rates: convert 500 EUR](38-fx-rates/) | metadata | 193 | 199 | 301 | 287 | 310 |
| 39 | [Reviews: rating of verified buyers](39-reviews-verified/) | metadata, needs metadata | 430 | 274 | 391 | 353 | 403 |
| 40 | [Office: rooms for 8 with a projector](40-meeting-rooms/) | metadata | 301 | 296 | 328 | 313 | 323 |
| 41 | [Portfolio: profit per position](41-portfolio-pnl/) | metadata | 300 | 236 | 351 | 331 | 344 |
| 42 | [Parking: free spots per level](42-parking-free/) | metadata, needs metadata | 580 | 321 | 476 | 427 | 447 |
| 43 | [Newsletter: campaigns above 25 % opens](43-newsletter-opens/) | metadata, needs metadata | 421 | 276 | 400 | 365 | 398 |
| 44 | [DNS zone: short TTLs](44-dns-ttl/) | metadata | 290 | 228 | 342 | 320 | 341 |
| 45 | [Timesheets: hours per project](45-timesheets-hours/) | metadata, needs metadata | 521 | 280 | 417 | 368 | 379 |
| 46 | [CI: failed runs per branch](46-ci-failures/) | metadata, needs metadata | 668 | 356 | 495 | 410 | 448 |
| 47 | [Nutrition: protein per portion](47-nutrition-protein/) | metadata, needs metadata | 241 | 206 | 317 | 304 | 334 |
| 48 | [Shop orders: status codes, cents and test orders](48-orders-meta/) | metadata, needs metadata | 684 | 377 | 534 | 469 | 593 |
| 49 | [Sensors: tenths of a degree, UTC times, calibrating](49-sensors-meta/) | metadata, needs metadata | 614 | 414 | 552 | 507 | 625 |
| 50 | [Staff: levels as codes, monthly salaries, contractors](50-staff-meta/) | metadata, needs metadata | 558 | 316 | 453 | 385 | 525 |
| 51 | [Inventory: reorder levels and discontinued items](51-inventory-meta/) | metadata, needs metadata | 478 | 283 | 419 | 374 | 464 |
| 52 | [Flat table: users](52-users-table/) | feature | 271 | 217 | 328 | 306 | – |
| 53 | [Nested records: orders with customer and items](53-nested-orders/) | feature | 383 | 329 | 389 | 362 | – |
| 54 | [Agent tool result: web search hits](54-tool-result/) | feature | 239 | 227 | 338 | 311 | – |
| 55 | [Time series: a week of metrics](55-time-series/) | feature | 386 | 284 | 404 | 374 | – |
| 56 | [Logs: which service is failing?](56-logs/) | feature | 419 | 289 | 407 | 371 | – |
| 57 | [Irregular data: a record that does not fit the header](57-irregular/) | feature | 213 | 233 | 324 | 304 | – |
| 58 | [Type overrides: values that differ from the header](58-type-override/) | feature | 206 | 200 | 308 | 298 | – |
| 59 | [Lists inside records: repositories with topics](59-lists-in-records/) | feature | 276 | 281 | 325 | 315 | – |
| 60 | [Lists of lists: a distance matrix](60-matrix/) | feature | 187 | 216 | 310 | 285 | – |
| 61 | [Missing values: support tickets](61-nulls/) | feature | 278 | 285 | 333 | 313 | – |
| 62 | [Names with spaces and symbols](62-special-names/) | feature | 190 | 201 | 300 | 296 | – |
| 63 | [Named types: @User defined once, used three times](63-named-types/) | feature, metadata | 197 | 214 | 312 | 296 | 308 |
| 64 | [Comments, attributes and tags](64-metadata/) | feature, metadata | 205 | 196 | 293 | 276 | 325 |
| 65 | [Schema and instance metadata](65-schema-metadata/) | feature, metadata | 231 | 252 | 317 | 308 | 401 |
| 66 | [Calendar: lists of [start, end] pairs](66-calendar/) | feature | 243 | 282 | 335 | 324 | – |
