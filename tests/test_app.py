import os
import tempfile
import unittest
from datetime import date, timedelta
from app import app, init_db, expiry_status

class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        app.config.update(TESTING=True, DATABASE=os.path.join(self.temp_dir.name, "test.db"), SECRET_KEY="test-secret")
        self.ctx = app.app_context()
        self.ctx.push()
        init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.ctx.pop()
        self.temp_dir.cleanup()

    def register_and_login(self, username="tester"):
        self.client.post("/register", data={"username": username, "password": "password123"})
        return self.client.post("/login", data={"username": username, "password": "password123"})

    def test_expiry_status_boundaries(self):
        today = date.today()
        self.assertEqual(expiry_status((today - timedelta(days=1)).isoformat(), today), "Expired")
        self.assertEqual(expiry_status(today.isoformat(), today), "Expiring Soon")
        self.assertEqual(expiry_status((today + timedelta(days=30)).isoformat(), today), "Expiring Soon")
        self.assertEqual(expiry_status((today + timedelta(days=31)).isoformat(), today), "Valid")

    def test_invalid_expiry_rejected(self):
        with self.assertRaises(ValueError):
            expiry_status("not-a-date")

    def test_api_requires_login(self):
        response = self.client.get("/api/documents")
        self.assertEqual(response.status_code, 401)

    def test_document_crud_api(self):
        self.register_and_login()
        payload = {"title": "Passport", "document_type": "Identity", "expiry_date": (date.today()+timedelta(days=60)).isoformat(), "notes": "Test"}
        created = self.client.post("/api/documents", json=payload)
        self.assertEqual(created.status_code, 201)
        doc_id = created.get_json()["id"]
        self.assertEqual(self.client.get("/api/documents").status_code, 200)
        changed = {**payload, "title": "Updated Passport"}
        self.assertEqual(self.client.put(f"/api/documents/{doc_id}", json=changed).status_code, 200)
        self.assertEqual(self.client.get(f"/api/documents/{doc_id}").get_json()["title"], "Updated Passport")
        self.assertEqual(self.client.delete(f"/api/documents/{doc_id}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/documents/{doc_id}").status_code, 404)

    def test_validation_rejects_missing_fields(self):
        self.register_and_login()
        response = self.client.post("/api/documents", json={"title": "Passport"})
        self.assertEqual(response.status_code, 400)

    def test_user_cannot_access_another_users_document(self):
        self.register_and_login("userone")
        payload = {"title": "Card", "document_type": "ID", "expiry_date": date.today().isoformat()}
        doc_id = self.client.post("/api/documents", json=payload).get_json()["id"]
        self.client.get("/logout")
        self.register_and_login("usertwo")
        self.assertEqual(self.client.get(f"/api/documents/{doc_id}").status_code, 404)

if __name__ == "__main__":
    unittest.main(verbosity=2)
