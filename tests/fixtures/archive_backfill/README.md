# Archive Backfill fixtures

One fixture per discovery or rehydration shape the Backfill has to survive, committed because an outlet changes its markup and a fixture is the record of what the rule was written against.
Each is a reduced copy of a real surveyed outlet's response, with the outlet's identity and article text replaced.

Used by `tests/unit/test_archive_backfill.py`.

| Fixture | Shape | What it pins |
|---------|-------|--------------|
| `01_monthly_archive_sitemap.xml` | A month of article URLs, each carrying its date in the path | Discovery filters by date without fetching anything, and a URL with no path date is not an article. |
| `02_paginated_feed_page_1.xml` | Page one of a feed walked backwards by a page parameter | The ordinary case, newest first. |
| `03_paginated_feed_page_2.xml` | Page two, older items, no overlap with page one | A walk continues while a page brings new URLs. |
| `04_paginated_feed_wraparound.xml` | Page one's content served again, with a 200 status | At least one surveyed topic feed does this once its real depth runs out. A crawler that stops only on an error loops forever and re-ingests the same items. |
| `05_topic_feed_page_1.xml` | A tag feed, dated by a suffix in the URL slug | A second pagination route, and a path date format the numeric patterns do not match. |
| `06_paginated_feed_page_before_window.xml` | A page whose every item predates the window | The walk stops because it has reached the date it was asked for, not because it hit the page cap. |
| `07_archive_snapshot.html` | A Wayback rehydration carrying the outlet's own JSON-LD | The body comes from the archive when the publisher returns a client error, and the date still comes from the document. |
| `08_undated_archive_snapshot.html` | A rehydration whose markup asserts no date | The capture time is known and is still never written as a Publication Time. |

The two HTML fixtures are fetched through the `id_` modifier, which returns the markup as served rather than the archive's rewritten copy.
