import unittest

from fastapi.testclient import TestClient

from app import ingestion, vectorstore
from app.config import settings
from app.main import app
from auth_helpers import auth_headers, patch_supabase_auth

SHA_TEXT = """
1. Board Composition. The Board shall comprise five (5) directors: two
appointed by Alpha Robotics Pte Ltd and three by Beta Ventures Ltd.

2. Transfer Restrictions. No shareholder may transfer shares without
first offering them to the other party on the same terms.

3. Indemnity. Each shareholder indemnifies the company against losses
arising from its own breach of this agreement, capped at the value of
its shareholding.

4. Deadlock. In the event of a deadlock at Board level, either party
may invoke the buy-sell procedure set out in Schedule 2.
"""


class ClauseSearchTests(unittest.TestCase):
    def setUp(self):
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            self.skipTest("SUPABASE_URL/SUPABASE_ANON_KEY not set -- copy them into backend/.env to run auth tests.")
        self._auth_patcher = patch_supabase_auth()
        self._auth_patcher.start()
        self.addCleanup(self._auth_patcher.stop)
        self._orig_partners = settings.PARTNER_EMAILS
        settings.PARTNER_EMAILS = {"partner@example.com"}
        self.addCleanup(lambda: setattr(settings, "PARTNER_EMAILS", self._orig_partners))
        vectorstore.reset()
        vectorstore.add_document("doc-sha", SHA_TEXT, {
            "filename": "sha_alpha_beta.txt",
            "client_name": "Alpha Robotics",
            "counterparty_name": "Beta Ventures",
            "matter_type": "shareholders agreement",
            "jurisdiction": "Singapore",
            "confidentiality": "internal",
        })
        vectorstore.add_document_clauses("doc-sha", ingestion.split_into_clauses(SHA_TEXT))
        self.client = TestClient(app)

    def test_clause_search_finds_the_specific_clause_not_just_the_document(self):
        res = self.client.post(
            "/api/search/clauses",
            json={"query": "cap on indemnity liability", "keep_top": 3},
            headers=auth_headers(),
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertGreater(len(body["kept"]), 0)
        top = body["kept"][0]
        self.assertEqual(top["doc_id"], "doc-sha")
        self.assertIn("Indemnity", top["label"])
        self.assertIn("capped", top["text"])

    def test_walled_matter_blocks_clause_results_too(self):
        matter_key = "alpha robotics|beta ventures|shareholders agreement|singapore"
        res = self.client.post(
            f"/api/matters/{matter_key}/wall",
            json={"walled": True, "allowed_emails": ["ally@example.com"]},
            headers=auth_headers("partner@example.com"),
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/search/clauses",
            json={"query": "cap on indemnity liability"},
            headers=auth_headers("outsider@example.com"),
        )
        body = res.json()
        self.assertEqual(len(body["kept"]), 0)
        self.assertTrue(any(r["doc_id"] == "doc-sha" for r in body["access_restricted"]))


if __name__ == "__main__":
    unittest.main()
