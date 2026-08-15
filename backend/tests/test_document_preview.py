import unittest

from fastapi.testclient import TestClient

from app import vectorstore
from app.main import app


class DocumentPreviewRouteTests(unittest.TestCase):
    def setUp(self):
        vectorstore.reset()
        vectorstore.add_document(
            "doc-1",
            "This is the full preview text for the selected document.",
            {
                "filename": "sample_agreement.txt",
                "matter_type": "shareholders agreement",
                "jurisdiction": "Singapore",
                "document_date": "2024-01-15",
                "version": "3",
                "partner_approved": True,
                "confidentiality": "internal",
            },
        )

    def test_get_document_returns_text_for_preview(self):
        client = TestClient(app)
        response = client.get("/api/documents/doc-1")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["doc_id"], "doc-1")
        self.assertEqual(body["filename"], "sample_agreement.txt")
        self.assertIn("full preview text", body["text"])


if __name__ == "__main__":
    unittest.main()
