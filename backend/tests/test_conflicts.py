import unittest

from fastapi.testclient import TestClient

from app import conflicts, matters, vectorstore
from app.config import settings
from app.main import app
from auth_helpers import auth_headers, patch_supabase_auth


class ConflictDetectionUnitTests(unittest.TestCase):
    """Pure-logic tests for conflicts.detect_conflicts -- no LLM, no HTTP,
    fast and deterministic, so the actual matching rules get real coverage."""

    def setUp(self):
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            self.skipTest("SUPABASE_URL/SUPABASE_ANON_KEY not set -- copy them into backend/.env to run auth tests.")
        vectorstore.reset()
        # Existing matter: Acme Corp v. Beta Holdings (a lease dispute).
        vectorstore.add_document("doc-existing", "lease dispute text", {
            "filename": "acme_v_beta.txt",
            "client_name": "Acme Corp",
            "counterparty_name": "Beta Holdings",
            "matter_type": "lease dispute",
            "jurisdiction": "Singapore",
        })

    def test_new_matters_counterparty_is_an_existing_client_flags_a_conflict(self):
        new_meta = {"client_name": "Gamma Ventures", "counterparty_name": "Acme Corp", "matter_type": "shareholders agreement"}
        new_key = matters.cluster_key(new_meta)
        found = conflicts.detect_conflicts(new_meta, new_key)
        self.assertEqual(len(found), 1)
        self.assertIn("Acme Corp", found[0]["reason"])
        self.assertIn("existing client", found[0]["reason"])

    def test_new_matters_client_is_an_existing_counterparty_flags_a_conflict(self):
        new_meta = {"client_name": "Beta Holdings", "counterparty_name": "Delta Retail", "matter_type": "tenancy agreement"}
        new_key = matters.cluster_key(new_meta)
        found = conflicts.detect_conflicts(new_meta, new_key)
        self.assertEqual(len(found), 1)
        self.assertIn("Beta Holdings", found[0]["reason"])

    def test_unrelated_matter_is_not_flagged(self):
        new_meta = {"client_name": "Zeta Robotics", "counterparty_name": "Omega Supplies", "matter_type": "supply agreement"}
        new_key = matters.cluster_key(new_meta)
        found = conflicts.detect_conflicts(new_meta, new_key)
        self.assertEqual(found, [])

    def test_documents_within_the_same_matter_are_not_self_flagged(self):
        # A later version of the SAME matter (same parties) must not
        # trigger a conflict against itself.
        new_meta = {"client_name": "Acme Corp", "counterparty_name": "Beta Holdings", "matter_type": "lease dispute", "jurisdiction": "Singapore"}
        new_key = matters.cluster_key(new_meta)
        found = conflicts.detect_conflicts(new_meta, new_key)
        self.assertEqual(found, [])


class ConflictApiTests(unittest.TestCase):
    """API-level tests for surfacing + acknowledging a flag -- conflict
    detection itself is seeded directly (see above for the logic tests),
    so these don't need a real LLM call through /api/ingest."""

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
        new_meta = {
            "filename": "gamma_sha.txt",
            "client_name": "Gamma Ventures",
            "counterparty_name": "Acme Corp",
            "matter_type": "shareholders agreement",
            "jurisdiction": "Singapore",
        }
        self.matter_key = matters.cluster_key(new_meta)
        vectorstore.add_document("doc-new", "shareholders agreement text", new_meta)
        vectorstore.flag_conflict(self.matter_key, "Acme Corp is an existing client elsewhere.", "doc-new")
        self.client = TestClient(app)

    def test_matters_endpoint_surfaces_the_unacknowledged_conflict_first(self):
        res = self.client.get("/api/matters", headers=auth_headers("partner@example.com"))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body[0]["conflict"] is not None)
        self.assertEqual(body[0]["matter_key"], self.matter_key)
        self.assertFalse(body[0]["conflict"]["acknowledged"])

    def test_non_partner_cannot_acknowledge(self):
        res = self.client.post(
            f"/api/matters/{self.matter_key}/conflict/acknowledge",
            headers=auth_headers("associate@example.com"),
        )
        self.assertEqual(res.status_code, 403)

    def test_partner_can_acknowledge_and_it_no_longer_shows_as_unresolved(self):
        res = self.client.post(
            f"/api/matters/{self.matter_key}/conflict/acknowledge",
            headers=auth_headers("partner@example.com"),
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["acknowledged"])
        self.assertEqual(res.json()["acknowledged_by"], "partner@example.com")

        res = self.client.get("/api/matters", headers=auth_headers("partner@example.com"))
        matter = next(m for m in res.json() if m["matter_key"] == self.matter_key)
        self.assertTrue(matter["conflict"]["acknowledged"])


if __name__ == "__main__":
    unittest.main()
