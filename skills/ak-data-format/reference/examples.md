# AK-DATA examples

Generated from `ak-data example`. Each example: what it shows, the AK-DATA,
the same data as JSON, a question and the expected answer (in AK-DATA).

## 52. Flat table: users

A list of records sharing one header: field names are written once, every record is a (…) tuple in header order. 

```akd
<users:<[
  id:number,
  name:string,
  email:string,
  role:string,
  active:bool
]>>
([
  (1, "Ada Lovelace", "ada@example.com", "admin", true),
  (2, "Alan Turing", "alan@example.com", "user", true),
  (3, "Grace Hopper", "grace@example.com", "admin", false),
  (4, "Linus Torvalds", "linus@example.com", "user", true),
  (5, "Margaret Hamilton", "margaret@example.com", "admin", true)
])
```

```json
{"users":[{"id":1,"name":"Ada Lovelace","email":"ada@example.com","role":"admin","active":true},{"id":2,"name":"Alan Turing","email":"alan@example.com","role":"user","active":true},{"id":3,"name":"Grace Hopper","email":"grace@example.com","role":"admin","active":false},{"id":4,"name":"Linus Torvalds","email":"linus@example.com","role":"user","active":true},{"id":5,"name":"Margaret Hamilton","email":"margaret@example.com","role":"admin","active":true}]}
```

**Question:** Which active users are admins?

```akd
<admins:<[id:number, name:string]>>
([(1, "Ada Lovelace"), (5, "Margaret Hamilton")])
```

## 53. Nested records: orders with customer and items

Headers nest: customer is a record <…> inside the record, items a list of records <[…]>; nested values stay positional. 

```akd
<orders:<[
  id:string,
  status:string,
  customer:<id:number, name:string, country:string>,
  items:<[sku:string, qty:number, price:number]>
]>>
([
  ("ORD-1001", "paid", (7, "Hedy Johnson", "PL"),
   [("KB-01", 2, 89.0), ("MS-02", 1, 39.5)]),
  ("ORD-1002", "pending", (9, "Ada Torvalds", "DE"),
   [("HD-10", 1, 129.9)]),
  ("ORD-1003", "paid", (7, "Hedy Johnson", "PL"),
   [("DK-05", 1, 199.0), ("KB-01", 1, 89.0)])
])
```

```json
{"orders":[{"id":"ORD-1001","status":"paid","customer":{"id":7,"name":"Hedy Johnson","country":"PL"},"items":[{"sku":"KB-01","qty":2,"price":89.0},{"sku":"MS-02","qty":1,"price":39.5}]},{"id":"ORD-1002","status":"pending","customer":{"id":9,"name":"Ada Torvalds","country":"DE"},"items":[{"sku":"HD-10","qty":1,"price":129.9}]},{"id":"ORD-1003","status":"paid","customer":{"id":7,"name":"Hedy Johnson","country":"PL"},"items":[{"sku":"DK-05","qty":1,"price":199.0},{"sku":"KB-01","qty":1,"price":89.0}]}]}
```

**Question:** What is the total (qty × price) of every paid order?

```akd
<paid:<[id:string, total:number]>>
([("ORD-1001", 217.5), ("ORD-1003", 288.0)])
```

## 54. Agent tool result: web search hits

A record with simple fields and a list of records — the typical tool output an agent puts back into the context. 

```akd
<
  tool:string,
  query:string,
  results:<[rank:number, title:string, url:string, score:number]>
>
(
  "web_search",
  "agent memory",
  [
    (1, "Agent memory in production", "https://example.org/a", 0.97),
    (2, "Token budgets for agents", "https://example.org/b", 0.94),
    (3, "Context engineering", "https://example.org/c", 0.88),
    (4, "Vector stores compared", "https://example.org/d", 0.71)
  ]
)
```

```json
{"tool":"web_search","query":"agent memory","results":[{"rank":1,"title":"Agent memory in production","url":"https://example.org/a","score":0.97},{"rank":2,"title":"Token budgets for agents","url":"https://example.org/b","score":0.94},{"rank":3,"title":"Context engineering","url":"https://example.org/c","score":0.88},{"rank":4,"title":"Vector stores compared","url":"https://example.org/d","score":0.71}]}
```

**Question:** Which results have a score of at least 0.9?

```akd
<hits:<[rank:number, url:string]>>
([(1, "https://example.org/a"), (2, "https://example.org/b")])
```

## 55. Time series: a week of metrics

Numbers stay numbers (no quotes); a time series is just a list of records with a date field. 

```akd
<
  metric:string,
  days:<[date:string, visits:number, signups:number, revenue:number]>
>
(
  "daily",
  [
    ("2026-10-19", 1840, 31, 1290.5),
    ("2026-10-20", 2210, 44, 1980.0),
    ("2026-10-21", 1975, 29, 1405.25),
    ("2026-10-22", 2650, 57, 2410.0),
    ("2026-10-23", 2390, 48, 2005.75),
    ("2026-10-24", 1210, 12, 640.0),
    ("2026-10-25", 1105, 15, 702.5)
  ]
)
```

```json
{"metric":"daily","days":[{"date":"2026-10-19","visits":1840,"signups":31,"revenue":1290.5},{"date":"2026-10-20","visits":2210,"signups":44,"revenue":1980.0},{"date":"2026-10-21","visits":1975,"signups":29,"revenue":1405.25},{"date":"2026-10-22","visits":2650,"signups":57,"revenue":2410.0},{"date":"2026-10-23","visits":2390,"signups":48,"revenue":2005.75},{"date":"2026-10-24","visits":1210,"signups":12,"revenue":640.0},{"date":"2026-10-25","visits":1105,"signups":15,"revenue":702.5}]}
```

**Question:** Which day had the most signups, and what was the revenue that day?

```akd
<best:<[date:string, signups:number, revenue:number]>>
([("2026-10-22", 57, 2410.0)])
```

## 56. Logs: which service is failing?

Repeated rows are where AK-DATA saves most: the five field names appear once instead of eight times. 

```akd
<events:<[
  ts:string,
  level:string,
  service:string,
  msg:string,
  ms:number
]>>
([
  ("12:00:01", "info", "api", "GET /orders", 42),
  ("12:00:03", "error", "billing", "card declined", 380),
  ("12:00:04", "warn", "api", "slow query", 1210),
  ("12:00:07", "error", "billing", "timeout", 5000),
  ("12:00:09", "info", "auth", "login ok", 18),
  ("12:00:11", "error", "api", "upstream 502", 2210),
  ("12:00:12", "error", "billing", "timeout", 5000),
  ("12:00:15", "info", "api", "GET /users", 37)
])
```

```json
{"events":[{"ts":"12:00:01","level":"info","service":"api","msg":"GET /orders","ms":42},{"ts":"12:00:03","level":"error","service":"billing","msg":"card declined","ms":380},{"ts":"12:00:04","level":"warn","service":"api","msg":"slow query","ms":1210},{"ts":"12:00:07","level":"error","service":"billing","msg":"timeout","ms":5000},{"ts":"12:00:09","level":"info","service":"auth","msg":"login ok","ms":18},{"ts":"12:00:11","level":"error","service":"api","msg":"upstream 502","ms":2210},{"ts":"12:00:12","level":"error","service":"billing","msg":"timeout","ms":5000},{"ts":"12:00:15","level":"info","service":"api","msg":"GET /users","ms":37}]}
```

**Question:** How many errors does each service have? Most errors first.

```akd
<errors:<[service:string, errors:number]>>
([("billing", 3), ("api", 1)])
```

## 57. Irregular data: a record that does not fit the header

The third agent has temperature instead of max_steps, so it is written as <any> {key:value} with its own keys — still lossless. 

```akd
<
  service:string,
  agents:<[name:string, tools:[string], max_steps:number]>,
  limits:<tokens:number, retries:[number]>,
  storage:null
>
(
  "workspace",
  [
    ("planner", ["search", "files", "calendar"], 12),
    ("writer", ["files"], 6),
    <any> {name:"reviewer", tools:["files", "search"], temperature:0.2}
  ],
  (120000, [1, 5, 30]),
  null
)
```

```json
{"service":"workspace","agents":[{"name":"planner","tools":["search","files","calendar"],"max_steps":12},{"name":"writer","tools":["files"],"max_steps":6},{"name":"reviewer","tools":["files","search"],"temperature":0.2}],"limits":{"tokens":120000,"retries":[1,5,30]},"storage":null}
```

**Question:** Which agent can use the most tools, and how many?

```akd
<agent:<[name:string, tools:number]>>
([("planner", 3)])
```

## 58. Type overrides: values that differ from the header

When one value has another type than its column, it is prefixed with <type> — <number> 3001, <string> "on order"; null fits every type. 

```akd
<products:<[sku:string, name:string, price:number, stock:number]>>
([
  ("KB-01", "Keyboard", 89.0, 14),
  ("MS-02", "Mouse", 39.5, 0),
  (<number> 3001, "USB cable", null, 120),
  ("HD-10", "Headset", 129.9, <string> "on order")
])
```

```json
{"products":[{"sku":"KB-01","name":"Keyboard","price":89.0,"stock":14},{"sku":"MS-02","name":"Mouse","price":39.5,"stock":0},{"sku":3001,"name":"USB cable","price":null,"stock":120},{"sku":"HD-10","name":"Headset","price":129.9,"stock":"on order"}]}
```

**Question:** Which products cannot be sold right now (no price, no stock, or stock not a number)?

```akd
<blocked:<[name:string]>>
([("Mouse"), ("USB cable"), ("Headset")])
```

## 59. Lists inside records: repositories with topics

A field can hold a list of values: topics:[string] in the header, ["llm","rust"] or [] in the record. 

```akd
<repositories:<[
  name:string,
  stars:number,
  topics:[string],
  archived:bool
]>>
([
  ("arkadia-data", 1840, ["llm", "json", "rust", "python"], false),
  ("ak-workspace", 920, ["agents", "electron"], false),
  ("toon-python", 310, ["llm", "python"], true),
  ("star-federation", 75, [], false),
  ("universal-timer", 210, ["rust", "cli"], false)
])
```

```json
{"repositories":[{"name":"arkadia-data","stars":1840,"topics":["llm","json","rust","python"],"archived":false},{"name":"ak-workspace","stars":920,"topics":["agents","electron"],"archived":false},{"name":"toon-python","stars":310,"topics":["llm","python"],"archived":true},{"name":"star-federation","stars":75,"topics":[],"archived":false},{"name":"universal-timer","stars":210,"topics":["rust","cli"],"archived":false}]}
```

**Question:** Which repositories that are not archived have the topic rust? Most stars first.

```akd
<repos:<[name:string, stars:number]>>
([("arkadia-data", 1840), ("universal-timer", 210)])
```

## 60. Lists of lists: a distance matrix

Nested lists need no header beyond [[number]]: rows are plain [ … ] lists. 

```akd
<name:string, cities:[string], km:[[number]]>
(
  "distance (km)",
  ["Warsaw", "Kraków", "Gdańsk", "Wrocław"],
  [
    [0, 293, 340, 344],
    [293, 0, 591, 269],
    [340, 591, 0, 482],
    [344, 269, 482, 0]
  ]
)
```

```json
{"name":"distance (km)","cities":["Warsaw","Kraków","Gdańsk","Wrocław"],"km":[[0,293,340,344],[293,0,591,269],[340,591,0,482],[344,269,482,0]]}
```

**Question:** Which two cities are farthest apart, and how far?

```akd
<pair:<[from:string, to:string, km:number]>>
([("Kraków", "Gdańsk", 591)])
```

## 61. Missing values: support tickets

A nested record that is missing is <null> null (or null): the header still describes the record when it is there. 

```akd
<tickets:<[
  id:number,
  subject:string,
  priority:string,
  assignee:<id:number, name:string>,
  tags:[string]
]>>
([
  (501, "Invoice is wrong", "normal", (3, "Ola"), ["billing"]),
  (502, "Cannot log in", "urgent", <null> null, ["auth"]),
  (503, "Data export fails", "urgent", (5, "Piotr"), ["export", "bug"]),
  (504, "App crashes on start", "urgent", <null> null,
   ["mobile", "bug"])
])
```

```json
{"tickets":[{"id":501,"subject":"Invoice is wrong","priority":"normal","assignee":{"id":3,"name":"Ola"},"tags":["billing"]},{"id":502,"subject":"Cannot log in","priority":"urgent","assignee":null,"tags":["auth"]},{"id":503,"subject":"Data export fails","priority":"urgent","assignee":{"id":5,"name":"Piotr"},"tags":["export","bug"]},{"id":504,"subject":"App crashes on start","priority":"urgent","assignee":null,"tags":["mobile","bug"]}]}
```

**Question:** Which urgent tickets have nobody assigned?

```akd
<unassigned:<[id:number, subject:string]>>
([(502, "Cannot log in"), (504, "App crashes on start")])
```

## 62. Names with spaces and symbols

Field names that are not simple identifiers go in backticks: `user id`, `e-mail`, `2fa`. 

```akd
<rows:<[
  `user id`:number,
  `e-mail`:string,
  `2fa`:bool,
  `last login`:string
]>>
([
  (17, "ada@example.com", true, "2026-10-28"),
  (18, "alan@example.com", false, "2026-09-02"),
  (19, "grace@example.com", false, "2026-10-27")
])
```

```json
{"rows":[{"user id":17,"e-mail":"ada@example.com","2fa":true,"last login":"2026-10-28"},{"user id":18,"e-mail":"alan@example.com","2fa":false,"last login":"2026-09-02"},{"user id":19,"e-mail":"grace@example.com","2fa":false,"last login":"2026-10-27"}]}
```

**Question:** Which users do not have 2FA enabled?

```akd
<no_2fa:<[user_id:number, email:string]>>
([(18, "alan@example.com"), (19, "grace@example.com")])
```

## 63. Named types: @User defined once, used three times

@User<…> names a header; lead:@User and members:[@User] reuse it. Hand-written AK-DATA (the encoder writes inline headers). 

```akd
/* Team directory: one type, used three times */
@User<id:number, name:string, email:string>
<team:string, lead:@User, members:[@User]>
(
  "platform",
  (1, "Ada Lovelace", "ada@example.com"),
  [
    (2, "Alan Turing", "alan@example.com"),
    (3, "Grace Hopper", "grace@example.com"),
    (4, "Linus Torvalds", "linus@example.com")
  ]
)
```

```json
{"team":"platform","lead":{"id":1,"name":"Ada Lovelace","email":"ada@example.com"},"members":[{"id":2,"name":"Alan Turing","email":"alan@example.com"},{"id":3,"name":"Grace Hopper","email":"grace@example.com"},{"id":4,"name":"Linus Torvalds","email":"linus@example.com"}]}
```

**Question:** How many people are in the team, including the lead? Give the team name too.

```akd
<team:<[name:string, people:number]>>
([("platform", 4)])
```

## 64. Comments, attributes and tags

/* comments */, $attr=value, #tags and // … // blocks are notes for the reader: they are skipped when decoding, the data is unchanged. 

```akd
// $source="crm" $exported="2026-10-29" #snapshot //
<customers:<[
  id:number /* primary key */,
  name:string,
  plan:string $values="free|pro|team",
  mrr:number /* monthly revenue, EUR */
]>>
([
  (1, "Acme", "team", 1200) #enterprise,
  (2, "Globex", "pro", 99),
  (3, "Initech", "free", 0) /* trial ended */,
  (4, "Umbrella", "team", 2400) #enterprise
])
```

```json
{"customers":[{"id":1,"name":"Acme","plan":"team","mrr":1200},{"id":2,"name":"Globex","plan":"pro","mrr":99},{"id":3,"name":"Initech","plan":"free","mrr":0},{"id":4,"name":"Umbrella","plan":"team","mrr":2400}]}
```

**Question:** What is the total monthly revenue (mrr) per plan? Highest first.

```akd
<mrr:<[plan:string, mrr:number]>>
([("team", 3600), ("pro", 99)])
```

## 65. Schema and instance metadata

Metadata on the header ($required, $unit, $maxItems, comments) describes every record; metadata on a value ($verified, #featured, #discontinued) describes one record. Both are skipped when decoding — the JSON is the same — but a model reads them. 

```akd
// $source="catalogue" $exported="2026-10-30" #snapshot //
/* Product catalogue: one named type with schema metadata */
@Product<[
  /* Schema metadata: rules for every product */
  sku:string $required /* stock keeping unit */,
  name:string $required,
  price:number $unit="EUR" $min=0,
  tags:[string] $maxItems=3
]>
<products:@Product>
([
  /* Instance metadata: facts about one product */
  $verified=true ("PROD-123", "Keyboard", 89.0, ["new", "wireless"]) #featured,
  ("PROD-124", "Mouse", 39.5, []),
  $verified=true ("PROD-125", "Dock", 199.0, ["usb-c"]),
  ("PROD-126", "Cable", 9.99, ["usb-c"]) #discontinued /* sold out, no restock */
])
```

```json
{"products":[{"sku":"PROD-123","name":"Keyboard","price":89.0,"tags":["new","wireless"]},{"sku":"PROD-124","name":"Mouse","price":39.5,"tags":[]},{"sku":"PROD-125","name":"Dock","price":199.0,"tags":["usb-c"]},{"sku":"PROD-126","name":"Cable","price":9.99,"tags":["usb-c"]}]}
```

**Question:** Which products are verified and not discontinued? Give the sku and the price in EUR.

```akd
<verified:<[sku:string, eur:number]>>
([("PROD-123", 89.0), ("PROD-125", 199.0)])
```

## 66. Calendar: lists of [start, end] pairs

Records can hold lists of lists; the header says busy:[[string]] once for every person. 

```akd
<
  date:string,
  people:<[name:string, busy:[[string]]]>,
  working_hours:[string]
>
(
  "2026-11-03",
  [
    ("Ada", [["09:00", "10:30"], ["13:00", "14:00"]]),
    ("Alan", [["10:00", "11:00"], ["15:00", "16:00"]]),
    ("Grace", [["09:00", "09:30"], ["11:00", "12:00"]])
  ],
  ["09:00", "17:00"]
)
```

```json
{"date":"2026-11-03","people":[{"name":"Ada","busy":[["09:00","10:30"],["13:00","14:00"]]},{"name":"Alan","busy":[["10:00","11:00"],["15:00","16:00"]]},{"name":"Grace","busy":[["09:00","09:30"],["11:00","12:00"]]}],"working_hours":["09:00","17:00"]}
```

**Question:** Which full hours (start on the hour, 60 minutes) are free for everyone?

```akd
<free:<[start:string]>>
([("12:00"), ("14:00"), ("16:00")])
```
