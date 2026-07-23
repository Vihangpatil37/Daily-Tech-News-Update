import unittest
from unittest.mock import patch, MagicMock
from app.agents import blog_agent, hackernews_agent, github_agent, devto_agent, arxiv_agent

class TestAgentsMocked(unittest.TestCase):

    @patch("feedparser.parse")
    def test_blog_agent_mocked(self, mock_parse):
        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda k, default="": {
            "title": "OpenAI GPT-5 Announcement",
            "link": "https://openai.com/blog/gpt-5",
            "summary": "Full summary text of release."
        }.get(k, default)
        mock_entry.published_parsed = None
        mock_entry.updated_parsed = None

        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [mock_entry]
        mock_parse.return_value = mock_feed

        items = blog_agent.fetch(24)
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)
        self.assertEqual(items[0].title, "OpenAI GPT-5 Announcement")

    @patch("requests.get")
    def test_hackernews_agent_mocked(self, mock_get):
        # Mock topstories.json response
        mock_top_resp = MagicMock()
        mock_top_resp.status_code = 200
        mock_top_resp.json.return_value = [10001]

        # Mock item details response
        mock_item_resp = MagicMock()
        mock_item_resp.status_code = 200
        import time
        mock_item_resp.json.return_value = {
            "type": "story",
            "title": "New LLM Benchmark Released",
            "url": "https://news.ycombinator.com/item?id=10001",
            "score": 250,
            "time": int(time.time()),
            "descendants": 45
        }

        mock_get.side_effect = [mock_top_resp, mock_item_resp]

        items = hackernews_agent.fetch(24)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "New LLM Benchmark Released")
        self.assertEqual(items[0].engagement_score, 250.0)

    @patch("requests.get")
    def test_github_agent_mocked(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        mock_resp.json.return_value = {
            "items": [
                {
                    "full_name": "vllm-project/vllm",
                    "description": "High-throughput LLM serving engine",
                    "html_url": "https://github.com/vllm-project/vllm",
                    "stargazers_count": 15000,
                    "created_at": now_iso,
                    "language": "Python"
                }
            ]
        }
        mock_get.return_value = mock_resp

        items = github_agent.fetch(24)
        self.assertIsInstance(items, list)

    @patch("requests.get")
    def test_github_agent_star_threshold(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        mock_resp.json.return_value = {
            "items": [
                {
                    "full_name": "user/high-star-repo",
                    "description": "Popular repo",
                    "html_url": "https://github.com/user/high-star-repo",
                    "stargazers_count": 120,
                    "created_at": now_iso,
                    "language": "Python"
                },
                {
                    "full_name": "user/low-star-repo",
                    "description": "Low star repo",
                    "html_url": "https://github.com/user/low-star-repo",
                    "stargazers_count": 5,  # Below MIN_STARS (50)
                    "created_at": now_iso,
                    "language": "Python"
                }
            ]
        }
        mock_get.return_value = mock_resp

        items = github_agent.fetch(24)
        trending_items = [it for it in items if it.source == "GitHub Trending"]
        self.assertEqual(len(trending_items), 1)
        self.assertIn("user/high-star-repo", trending_items[0].title)

    @patch("requests.get")
    def test_devto_agent_mocked(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        mock_resp.json.return_value = [
            {
                "id": 12345,
                "title": "Evaluating LLM Agent Benchmarks",
                "canonical_url": "https://dev.to/user/evaluating-llm-agents",
                "published_at": now_iso,
                "description": "Comprehensive evaluation framework for LLM agents.",
                "positive_reactions_count": 42,
                "comments_count": 5
            }
        ]
        mock_get.return_value = mock_resp

        items = devto_agent.fetch(24)
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)
        self.assertEqual(items[0].title, "Evaluating LLM Agent Benchmarks")
        self.assertEqual(items[0].source, "Dev.to")
        self.assertEqual(items[0].engagement_score, 52.0)  # 42 + 5*2

    @patch("feedparser.parse")
    def test_arxiv_agent_mocked(self, mock_parse):
        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda k, default="": {
            "title": "Reasoning Models in LLM Agent Architectures",
            "link": "https://arxiv.org/abs/2401.12345",
            "summary": "Abstract of research paper."
        }.get(k, default)
        mock_entry.published_parsed = None

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]
        mock_parse.return_value = mock_feed

        items = arxiv_agent.fetch(24)
        self.assertIsInstance(items, list)


if __name__ == "__main__":
    unittest.main()
