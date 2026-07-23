import unittest
from app.models import RawItem
from app.services import dedup, db

class TestDeduplication(unittest.TestCase):

    def test_title_similarity_clustering(self):
        items = [
            RawItem(
                title="OpenAI Releases GPT-5 with Multimodal Reasoning",
                url="https://openai.com/blog/gpt-5-release",
                source="OpenAI Blog",
                published_at="2026-07-23T10:00:00Z",
                raw_summary="OpenAI announces GPT-5 model today.",
                engagement_score=100.0
            ),
            RawItem(
                title="OpenAI releases GPT-5 with multimodal reasoning!",
                url="https://news.ycombinator.com/item?id=12345",
                source="Hacker News",
                published_at="2026-07-23T10:30:00Z",
                raw_summary="Discussion on HN about GPT-5 release.",
                engagement_score=350.0
            )
        ]

        consolidated = dedup.deduplicate(items, enable_cross_day=False)
        self.assertEqual(len(consolidated), 1)
        item = consolidated[0]
        self.assertEqual(item.engagement_score, 350.0)
        self.assertIn("OpenAI Blog", item.sources)
        self.assertIn("Hacker News", item.sources)

    def test_distinct_items_not_clustered(self):
        items = [
            RawItem(
                title="Google DeepMind announces AlphaFold 3 update",
                url="https://deepmind.google/alphafold-3",
                source="Google DeepMind",
                published_at="2026-07-23T09:00:00Z",
                raw_summary="New structural prediction features.",
                engagement_score=80.0
            ),
            RawItem(
                title="Anthropic introduces Claude 3.5 Sonnet updates",
                url="https://anthropic.com/claude-3-5-sonnet",
                source="Anthropic News",
                published_at="2026-07-23T09:15:00Z",
                raw_summary="Performance improvements across benchmarks.",
                engagement_score=90.0
            )
        ]

        consolidated = dedup.deduplicate(items, enable_cross_day=False)
        self.assertEqual(len(consolidated), 2)


if __name__ == "__main__":
    unittest.main()
