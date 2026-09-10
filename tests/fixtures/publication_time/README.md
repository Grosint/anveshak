# Publication Time extraction fixtures

One file per outlet markup shape, twenty in total, covering every date signal and every
parsing hazard measured across the target outlet set for issue #42.

Each fixture is a reduced document: the head metadata, the time element and the visible
date stamp are kept because the extraction rules read them, and the article body, styling
and advertising markup are dropped because no rule reads them.
They are hand-authored records of the markup shape rather than verbatim captures, so a
fixture proves a rule rather than proving what one outlet served on one day.
When the corpus collection run replaces one with a verbatim capture, keep the file name so
the table in `tests/unit/test_publication_time_extraction.py` still resolves.

Fixtures are committed on purpose.
Outlet markup changes, and the fixture is the record of what the rule was written against.

| Fixture | Records |
|---------|---------|
| 01 | JSON-LD `NewsArticle` with an explicit offset, the common case |
| 02 | JSON-LD `@graph`, where the article type is `ReportageNewsArticle` and a `WebPage` node carries a decoy date |
| 03 | JSON-LD as a top-level array, with `@type` itself a list |
| 04 | Two JSON-LD blocks that disagree, only one carrying an offset |
| 05 | No JSON-LD at all, `article:published_time` on a `property` attribute |
| 06 | `article:published_time` on a `name` attribute |
| 07 | Non-standard `publish-date` meta name |
| 08 | Dublin Core `DC.date.issued` |
| 09 | Analytics vendor `parsely-pub-date` |
| 10 | `og:published_time` |
| 11 | `time` element with a `datetime` attribute carrying an offset |
| 12 | `time` element with the attribute spelled `dateTime` |
| 13 | Epoch in a data attribute, no `datetime` attribute, a visible date that is wrong by a fixed offset, and comment and related-story widgets carrying the same attribute names |
| 14 | Epoch in milliseconds |
| 15 | Single-digit timezone offset, which standard ISO parsing rejects |
| 16 | Non-ISO pseudo-zone suffix |
| 17 | Naive value that means UTC, displayed as IST |
| 18 | Naive value that means IST |
| 19 | Naive value with no declared timezone for the outlet |
| 20 | No date signal in the document, date encoded in the URL path |
