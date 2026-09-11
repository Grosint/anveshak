"""Virtual clock guard — issue #46, ADR 0003.

The clock override exists so that a Replay can run detection at the date the
evidence existed. These tests pin the property that it cannot be reached in a
live deployment: the flag is off by default, an override without the flag is
refused rather than ignored, and a naive timestamp is refused rather than
guessed into a zone.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from anveshak.clock import (
    ClockOverrideRefusedError,
    ClockSettings,
    describe_clock,
    parse_reference_time,
    resolve_reference_time,
)

pytestmark = pytest.mark.unit

REPLAY_TIME = datetime(2026, 5, 16, 9, 30, tzinfo=UTC)
IST = timezone(timedelta(hours=5, minutes=30))


def _settings(enabled: bool, environment: str = "test") -> ClockSettings:
    return ClockSettings(virtual_clock_enabled=enabled, environment=environment)


class TestDefaultIsTheWallClock:
    """Omitting the parameter is the live path, and it is the only path a
    deployment ever takes."""

    def test_no_reference_time_returns_the_current_time(self):
        before = datetime.now(UTC)
        resolved = resolve_reference_time()
        after = datetime.now(UTC)

        assert before <= resolved <= after

    def test_the_default_is_timezone_aware_utc(self):
        assert resolve_reference_time().tzinfo is UTC

    def test_the_default_needs_no_flag(self):
        # Settings with the flag off still resolve, because nothing was
        # overridden. A guard that refused here would break live operation.
        assert resolve_reference_time(None, settings=_settings(False)) is not None


class TestOverrideIsRefusedByDefault:
    """Deny by default, the same shape as the cloud model guard (ADR 0002)."""

    def test_an_override_without_the_flag_is_refused(self):
        with pytest.raises(ClockOverrideRefusedError) as exc:
            resolve_reference_time(REPLAY_TIME, settings=_settings(False))

        assert "VIRTUAL_CLOCK_ENABLED" in str(exc.value)

    def test_the_flag_defaults_to_off(self, monkeypatch):
        monkeypatch.delenv("VIRTUAL_CLOCK_ENABLED", raising=False)
        assert ClockSettings().virtual_clock_enabled is False

    def test_the_flag_comes_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("VIRTUAL_CLOCK_ENABLED", "true")
        assert ClockSettings().virtual_clock_enabled is True


class TestEnvironmentIsAnAllowlist:
    """One flag is one layer. A Replay .env copied onto a production host
    would otherwise be the whole gate."""

    @pytest.mark.parametrize(
        "environment", ["production", "prod", "staging", "preprod", "prod-dr", "uat", ""]
    )
    def test_an_environment_outside_the_allowlist_is_refused(self, environment):
        with pytest.raises(ClockOverrideRefusedError) as exc:
            resolve_reference_time(REPLAY_TIME, settings=_settings(True, environment))

        assert "VIRTUAL_CLOCK_ALLOWED_ENVIRONMENTS" in str(exc.value)

    def test_the_allowlist_is_configuration(self):
        settings = ClockSettings(
            virtual_clock_enabled=True,
            environment="ci",
            virtual_clock_allowed_environments=["ci"],
        )

        assert resolve_reference_time(REPLAY_TIME, settings=settings) == REPLAY_TIME

    def test_a_replay_deployment_is_on_the_allowlist_by_default(self):
        assert "replay" in ClockSettings().virtual_clock_allowed_environments

    def test_the_live_path_is_unaffected_by_the_environment(self):
        # Nothing was overridden, so there is nothing to refuse.
        assert resolve_reference_time(None, settings=_settings(True, "production")) is not None


class TestTheReferenceTimeIsInThePast:
    def test_a_future_reference_time_is_refused(self):
        ahead = datetime.now(UTC) + timedelta(days=1)

        with pytest.raises(ClockOverrideRefusedError) as exc:
            resolve_reference_time(ahead, settings=_settings(True))

        assert "future" in str(exc.value).lower()


class TestStartupDisclosure:
    """A capability that can date a Signal to a day it was not produced on
    says so at startup, not only when it is used."""

    def test_the_default_reports_the_system_clock_and_why(self):
        described = describe_clock(_settings(False))

        assert described["clock"] == "system"
        assert "VIRTUAL_CLOCK_ENABLED" in described["reason"]

    def test_a_permitted_override_reports_the_virtual_clock(self):
        assert describe_clock(_settings(True))["clock"] == "virtual"

    def test_a_refused_configuration_still_describes_itself(self):
        # Never raises: startup disclosure must survive a configuration that
        # resolve_reference_time refuses.
        described = describe_clock(_settings(True, "production"))

        assert described["clock"] == "refused"
        assert "VIRTUAL_CLOCK_ALLOWED_ENVIRONMENTS" in described["reason"]


class TestOverrideWithTheFlagOn:
    def test_the_supplied_time_is_returned(self):
        assert resolve_reference_time(REPLAY_TIME, settings=_settings(True)) == REPLAY_TIME

    def test_another_offset_is_normalised_to_utc(self):
        ist_noon = datetime(2026, 7, 20, 12, 0, tzinfo=IST)

        resolved = resolve_reference_time(ist_noon, settings=_settings(True))

        assert resolved.tzinfo is UTC
        assert resolved == datetime(2026, 7, 20, 6, 30, tzinfo=UTC)

    def test_a_naive_timestamp_is_refused(self):
        # Same reason the corpus importer refuses one: a guessed zone moves
        # items into the wrong day, and a day is the unit an analyst reads.
        with pytest.raises(ClockOverrideRefusedError) as exc:
            resolve_reference_time(datetime(2026, 5, 16, 9, 30), settings=_settings(True))

        assert "naive" in str(exc.value).lower()


class TestParsingAJobArgument:
    """ARQ job arguments carry the reference time as a string, so the parse
    step is where a typo must stop."""

    def test_none_stays_none(self):
        assert parse_reference_time(None) is None

    def test_an_iso_timestamp_with_an_offset_parses(self):
        parsed = parse_reference_time("2026-05-16T09:30:00+00:00", settings=_settings(True))
        assert parsed == REPLAY_TIME

    def test_a_datetime_passes_through(self):
        assert parse_reference_time(REPLAY_TIME, settings=_settings(True)) == REPLAY_TIME

    def test_parsing_applies_the_guard_too(self):
        # The guard runs at the job boundary as well as at the entry point, so
        # a parsed value is never an unguarded datetime in a caller's hand.
        with pytest.raises(ClockOverrideRefusedError):
            parse_reference_time("2026-05-16T09:30:00+00:00", settings=_settings(False))

    def test_a_naive_iso_timestamp_is_refused(self):
        with pytest.raises(ClockOverrideRefusedError):
            parse_reference_time("2026-05-16T09:30:00")

    def test_an_unparseable_value_is_refused(self):
        # Never falls back to the wall clock. A Replay stage that silently ran
        # live would date every Signal the day of the run.
        with pytest.raises(ClockOverrideRefusedError):
            parse_reference_time("last tuesday")

    def test_an_empty_string_is_refused(self):
        with pytest.raises(ClockOverrideRefusedError):
            parse_reference_time("")
