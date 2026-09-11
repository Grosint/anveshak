"""Outbound HTTP for addresses chosen by scraped content.

`url_safety` judges an address, `safe_fetch` is the path every request built on
that judgement takes. They live in the SDK rather than in the scraper because
the web, RSS, dark web and media paths all fetch addresses written by whoever
we are collecting from, and the media path is here.
"""
