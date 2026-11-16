"""Integration tests for the Flask app. Run with:  python -m unittest -v"""
import tempfile
import unittest
from pathlib import Path

from portfolio import create_app

GOOD = {"name": "Asha Rao", "email": "asha@example.com",
        "message": "Hi Praneeth, we have an ML internship open."}


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE": str(Path(self.tmp.name) / "test.db"),
            "ADMIN_TOKEN": "s3cret",
            "CONTACT_LIMIT_PER_HOUR": 3,
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()


class PageTests(AppTestCase):
    def test_index_renders_content_from_python_data(self):
        html = self.client.get("/").get_data(as_text=True)
        for text in ("Praneeth Reddy Kadavakolla", "My Manga Tracker", "Neon Arena",
                     "Python Learning", "Semester 2"):
            self.assertIn(text, html)

    def test_security_headers(self):
        response = self.client.get("/")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_unknown_page_is_html_404(self):
        response = self.client.get("/nope")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Page not found", response.get_data(as_text=True))

    def test_robots_and_sitemap(self):
        self.assertIn("Disallow: /api/", self.client.get("/robots.txt").get_data(as_text=True))
        self.assertIn("<urlset", self.client.get("/sitemap.xml").get_data(as_text=True))


class ContentApiTests(AppTestCase):
    def test_health(self):
        self.assertEqual(self.client.get("/api/health").get_json(),
                         {"status": "ok", "messages": 0})

    def test_projects_and_filter(self):
        data = self.client.get("/api/projects").get_json()
        self.assertEqual(data["count"], len(data["projects"]))
        flask_only = self.client.get("/api/projects?tech=flask").get_json()
        self.assertEqual([p["slug"] for p in flask_only["projects"]], ["portfolio-backend"])

    def test_project_detail_and_json_404(self):
        self.assertEqual(self.client.get("/api/projects/neon-arena").get_json()["title"],
                         "Neon Arena")
        response = self.client.get("/api/projects/missing")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Not Found")

    def test_skills_and_profile(self):
        self.assertIn("Languages", self.client.get("/api/skills").get_json()["skills"])
        self.assertEqual(self.client.get("/api/profile").get_json()["github_user"], "praneeth3112")


class ContactApiTests(AppTestCase):
    def test_valid_message_is_stored_and_readable_by_admin(self):
        response = self.client.post("/api/contact", json=GOOD)
        self.assertEqual(response.status_code, 201)
        stored = self.client.get("/api/messages", headers={"X-Admin-Token": "s3cret"}).get_json()
        self.assertEqual(stored["messages"][0]["email"], "asha@example.com")

    def test_invalid_message_returns_field_errors(self):
        response = self.client.post("/api/contact", json={"name": "A", "email": "bad", "message": "hi"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(set(response.get_json()["fields"]), {"name", "email", "message"})

    def test_honeypot_rejects_bots(self):
        response = self.client.post("/api/contact", json={**GOOD, "website": "http://spam"})
        self.assertEqual(response.status_code, 422)

    def test_non_json_body_is_rejected(self):
        response = self.client.post("/api/contact", data="plain", content_type="text/plain")
        self.assertEqual(response.status_code, 422)

    def test_rate_limit_after_three_messages(self):
        codes = [self.client.post("/api/contact", json=GOOD).status_code for _ in range(4)]
        self.assertEqual(codes, [201, 201, 201, 429])
        self.assertIn("Retry-After", self.client.post("/api/contact", json=GOOD).headers)

    def test_admin_endpoint_requires_token(self):
        self.assertEqual(self.client.get("/api/messages").status_code, 401)
        self.assertEqual(
            self.client.get("/api/messages", headers={"X-Admin-Token": "wrong"}).status_code, 401)

    def test_admin_endpoint_disabled_without_token_config(self):
        app = create_app({"TESTING": True, "DATABASE": str(Path(self.tmp.name) / "b.db"),
                          "ADMIN_TOKEN": ""})
        self.assertEqual(app.test_client().get("/api/messages").status_code, 404)


if __name__ == "__main__":
    unittest.main()
