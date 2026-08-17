import unittest

from fastapi.testclient import TestClient

from app import vectorstore
from app.config import settings
from app.main import app
from auth_helpers import auth_headers, patch_supabase_auth

MATTER_KEY = "alpha robotics|beta ventures|shareholders agreement|singapore"


class MatterWallTests(unittest.TestCase):
    def setUp(self):
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            self.skipTest("SUPABASE_URL/SUPABASE_ANON_KEY not set -- copy them into backend/.env to run auth tests.")
        self._auth_patcher = patch_supabase_auth()
        self._auth_patcher.start()
        self.addCleanup(self._auth_patcher.stop)
        vectorstore.reset()
        self._orig_partners = settings.PARTNER_EMAILS
        settings.PARTNER_EMAILS = {"partner@example.com"}
        vectorstore.add_document("doc-a", "alpha robotics shareholders agreement text", {
            "filename": "alpha_v1.txt",
            "client_name": "Alpha Robotics",
            "counterparty_name": "Beta Ventures",
            "matter_type": "shareholders agreement",
            "jurisdiction": "Singapore",
            "confidentiality": "internal",
        })
        self.client = TestClient(app)

    def tearDown(self):
        settings.PARTNER_EMAILS = self._orig_partners

    def test_unauthenticated_request_is_rejected(self):
        res = self.client.post("/api/search", json={"query": "shareholders agreement"})
        self.assertEqual(res.status_code, 401)

    def test_non_partner_cannot_set_wall(self):
        res = self.client.post(
            f"/api/matters/{MATTER_KEY}/wall",
            json={"walled": True, "allowed_emails": ["ally@example.com"]},
            headers=auth_headers("associate@example.com"),
        )
        self.assertEqual(res.status_code, 403)

    def test_walled_matter_blocks_outsider_and_admits_allowed_viewer(self):
        res = self.client.post(
            f"/api/matters/{MATTER_KEY}/wall",
            json={"walled": True, "allowed_emails": ["ally@example.com"]},
            headers=auth_headers("partner@example.com"),
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/search", json={"query": "shareholders agreement"},
            headers=auth_headers("outsider@example.com"),
        )
        body = res.json()
        self.assertTrue(any(i["doc_id"] == "doc-a" for i in body["access_restricted"]))
        self.assertFalse(any(i["doc_id"] == "doc-a" for i in body["kept"] + body["other_candidates"]))

        res = self.client.get("/api/documents", headers=auth_headers("ally@example.com"))
        self.assertTrue(any(d["doc_id"] == "doc-a" for d in res.json()))

        res = self.client.get("/api/documents/doc-a", headers=auth_headers("outsider@example.com"))
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
