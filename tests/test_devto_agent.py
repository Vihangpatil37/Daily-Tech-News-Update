import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from app.agents import devto_agent

class TestDevtoAgent(unittest.TestCase):

    @patch("requests.get")
    def test_fetch_devto_articles(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        now_iso = datetime.now(timezone.utc).isoformat()
        
        mock_resp.json.return_value = [
            {
                "id": 1001,
                "title": "Building Autonomous AI Agents with Python",
                "canonical_url": "https://dev.to/author/building-ai-agents",
                "published_at": now_iso,
                "description": "A guide on building agentic systems.",
                "positive_reactions_count": 50,
                "comments_count": 10
            }
        ]
        mock_get.return_value = mock_resp

        items = devto_agent.fetch(lookback_hours=24)
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)
        self.assertEqual(items[0].title, "Building Autonomous AI Agents with Python")
        self.assertEqual(items[0].url, "https://dev.to/author/building-ai-agents")
        self.assertEqual(items[0].source, "Dev.to")
        self.assertEqual(items[0].engagement_score, 70.0)  # 50 + 10*2

    @patch("requests.get")
    def test_fetch_devto_deduplication(self, mock_get):
        # Same article returned for multiple tags
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        now_iso = datetime.now(timezone.utc).isoformat()
        
        mock_resp.json.return_value = [
            {
                "id": 1001,
                "title": "Building Autonomous AI Agents with Python",
                "canonical_url": "https://dev.to/author/building-ai-agents",
                "published_at": now_iso,
                "description": "A guide on building agentic systems.",
                "positive_reactions_count": 50,
                "comments_count": 10
            }
        ]
        mock_get.return_value = mock_resp

        items = devto_agent.fetch(lookback_hours=24)
        # Multiple queries returned the same article ID 1001, should be deduplicated to 1 item
        self.assertEqual(len(items), 1)

    @patch("requests.get")
    def test_fetch_devto_error_handling(self, mock_get):
        mock_get.side_effect = Exception("Network connection failed")
        items = devto_agent.fetch(lookback_hours=24)
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
