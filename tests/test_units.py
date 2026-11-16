"""Unit tests for validators, the rate limiter, the GitHub service and content."""
import unittest
import urllib.error

from portfolio import content
from portfolio.services.github import GitHubService, language_breakdown, summarise_repo
from portfolio.services.ratelimit import SlidingWindowLimiter
from portfolio.validators import ValidationError, clean_text, validate_contact


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class ValidatorTests(unittest.TestCase):
    def test_clean_text_strips_control_chars_and_space(self):
        self.assertEqual(clean_text("  hi\x00 there\x07 "), "hi there")
        self.assertEqual(clean_text(None), "")

    def test_valid_payload_is_normalised(self):
        out = validate_contact({"name": " Asha ", "email": "ASHA@Example.COM",
                                "message": "A long enough message."})
        self.assertEqual(out["email"], "asha@example.com")
        self.assertEqual(out["name"], "Asha")

    def test_each_field_reports_its_own_error(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_contact({"name": "", "email": "x@y", "message": "short"})
        self.assertEqual(set(ctx.exception.errors), {"name", "email", "message"})

    def test_message_upper_bound(self):
        with self.assertRaises(ValidationError):
            validate_contact({"name": "Asha", "email": "a@b.co", "message": "x" * 2001})

    def test_non_dict_payload(self):
        with self.assertRaises(ValidationError):
            validate_contact(["not", "a", "dict"])


class RateLimiterTests(unittest.TestCase):
    def test_blocks_then_recovers_after_window(self):
        clock = FakeClock()
        limiter = SlidingWindowLimiter(2, window=60, clock=clock)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))
        self.assertGreater(limiter.retry_after("a"), 0)
        clock.now = 61
        self.assertTrue(limiter.allow("a"))

    def test_keys_are_independent(self):
        limiter = SlidingWindowLimiter(1, window=60, clock=FakeClock())
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("b"))

    def test_bad_arguments(self):
        with self.assertRaises(ValueError):
            SlidingWindowLimiter(0)


RAW = [
    {"name": "a", "language": "Python", "stargazers_count": 2, "html_url": "u1",
     "pushed_at": "2026-10-01T00:00:00Z", "description": None},
    {"name": "b", "language": "HTML", "stargazers_count": 0, "html_url": "u2",
     "pushed_at": "2026-11-01T00:00:00Z", "description": "site"},
    {"name": "forked", "language": "C", "fork": True, "pushed_at": "2026-11-05T00:00:00Z"},
]


class GitHubServiceTests(unittest.TestCase):
    def make(self, fetcher, clock=None):
        return GitHubService("someone", ttl=100, fetcher=fetcher, clock=clock or FakeClock())

    def test_filters_forks_and_sorts_newest_first(self):
        result = self.make(lambda url, t: RAW).repos()
        self.assertEqual([r["name"] for r in result["repos"]], ["b", "a"])
        self.assertEqual(result["source"], "live")
        self.assertEqual(result["languages"], {"Python": 1, "HTML": 1})

    def test_second_call_hits_cache(self):
        calls = []
        service = self.make(lambda url, t: calls.append(url) or RAW)
        service.repos()
        self.assertEqual(service.repos()["source"], "cache")
        self.assertEqual(len(calls), 1)

    def test_serves_stale_data_when_github_fails(self):
        clock = FakeClock()
        state = {"fail": False}

        def fetcher(url, timeout):
            if state["fail"]:
                raise urllib.error.URLError("down")
            return RAW

        service = self.make(fetcher, clock)
        service.repos()
        clock.now, state["fail"] = 500, True
        result = service.repos()
        self.assertEqual(result["source"], "stale")
        self.assertEqual(len(result["repos"]), 2)

    def test_unavailable_when_never_succeeded(self):
        def boom(url, timeout):
            raise urllib.error.URLError("down")
        result = self.make(boom).repos()
        self.assertEqual(result, {"repos": [], "languages": {}, "source": "unavailable"})

    def test_helpers(self):
        self.assertEqual(summarise_repo(RAW[0])["description"], "")
        self.assertEqual(summarise_repo(RAW[0])["updated"], "2026-10-01")
        self.assertEqual(language_breakdown([{"language": None}]), {})


class ContentTests(unittest.TestCase):
    def test_slugs_are_unique(self):
        slugs = [p.slug for p in content.PROJECTS]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_find_project(self):
        self.assertIsNone(content.find_project("nope"))
        self.assertEqual(content.find_project("neon-arena").title, "Neon Arena")

    def test_tech_frequency_is_sorted_by_use(self):
        counts = content.tech_frequency()
        values = list(counts.values())
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertEqual(counts["Python"], 2)

    def test_every_link_is_https(self):
        for project in content.PROJECTS:
            for link in project.links:
                self.assertTrue(link.url.startswith("https://"), link.url)


if __name__ == "__main__":
    unittest.main()
