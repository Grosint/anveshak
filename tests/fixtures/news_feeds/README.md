# News feed fixtures

One fixture per feed shape the news source adapter has to survive, committed because outlet feeds change and a fixture is the record of what the rule was written against.
Each is a reduced copy of a real surveyed outlet's markup, with the outlet's identity and article text replaced.

Used by `tests/unit/test_news_feed_adapter.py`.

| Fixture | Shape | What it pins |
|---------|-------|--------------|
| `01_full_text_feed.xml` | `content:encoded` carrying genuine article text | The body is used as served and no article is fetched. Five of the surveyed outlets deliver real full text this way. |
| `02_summary_only_feed.xml` | `description` of one to two hundred characters, no content element | A body below the threshold triggers an article fetch. This is the common case. |
| `03_empty_content_element_feed.xml` | `content:encoded` on every item, always empty | The element's presence is not the presence of text. Its wrapper markup is longer than the threshold and carries none, so measuring the markup stores an empty body. Item one still has a usable description and must fall back to it; item two does not and must trigger a fetch. |
| `04_atom_updated_only_feed.xml` | Atom, `updated` and never `published` | Reading only `published` leaves the whole outlet undated. |
| `05_undated_feed.xml` | No date on any item | Publication Time comes from the article document, and stays NULL when the document asserts none. Never the collection time. |

The bodies in `01` and `03` are HTML fragments, as feeds actually deliver them.
Tags are not content: the adapter stores their text, and an assertion that no stored body contains markup is part of the suite.
