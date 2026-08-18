import unittest

from fastapi.testclient import TestClient

from app import vectorstore
from app.config import settings
from app.main import app
from auth_helpers import auth_headers, patch_supabase_auth


class DocumentDeleteTests(unittest.TestCase):
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
        vectorstore.add_document("doc-to-delete", "some agreement text", {
            "filename": "delete_me.txt",
            "client_name": "Solo Client",
            "matter_type": "nda",
            "confidentiality": "internal",
        })
        self.client = TestClient(app)

    def test_non_partner_cannot_delete(self):
        res = self.client.delete("/api/documents/doc-to-delete", headers=auth_headers("associate@example.com"))
        self.assertEqual(res.status_code, 403)
        # still there
        self.assertIsNotNone(vectorstore.get_by_id("doc-to-delete"))

    def test_partner_can_delete_and_it_is_gone(self):
        res = self.client.delete("/api/documents/doc-to-delete", headers=auth_headers("partner@example.com"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "deleted")
        self.assertIsNone(vectorstore.get_by_id("doc-to-delete"))

        res = self.client.get("/api/documents", headers=auth_headers("partner@example.com"))
        self.assertFalse(any(d["doc_id"] == "doc-to-delete" for d in res.json()))

    def test_deleting_unknown_doc_id_is_404(self):
        res = self.client.delete("/api/documents/does-not-exist", headers=auth_headers("partner@example.com"))
        self.assertEqual(res.status_code, 404)

    def test_partner_cannot_delete_from_a_matter_they_are_walled_out_of(self):
        matter_key = "|".join(sorted(["solo client"])) + "|nda|"
        # Wall the matter, allowing only some other email -- not our partner.
        vectorstore.set_wall(matter_key, True, ["ally@example.com"], "partner@example.com")
        res = self.client.delete("/api/documents/doc-to-delete", headers=auth_headers("partner@example.com"))
        self.assertEqual(res.status_code, 403)
        self.assertIsNotNone(vectorstore.get_by_id("doc-to-delete"))


if __name__ == "__main__":
    unittest.main()
