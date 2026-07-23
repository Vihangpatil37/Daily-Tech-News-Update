import unittest
from app.models import ConsolidatedItem
from app.services import ranking

class TestRanking(unittest.TestCase):

    def test_ranking_keyword_and_engagement_boost(self):
        items = [
            ConsolidatedItem(
                id="1",
                title="Minor blog update on website CSS styling",
                url="https://example.com/css-update",
                sources=["Tech Blog"],
                published_at="2026-07-23T10:00:00Z",
                raw_summary="Fixed minor font rendering issue on home page.",
                engagement_score=5.0
            ),
            ConsolidatedItem(
                id="2",
                title="Critical Security Vulnerability CVE-2026-1000 GA Release in Open Source LLM Framework",
                url="https://example.com/cve-release",
                sources=["Hacker News", "GitHub Trending"],
                published_at="2026-07-23T10:00:00Z",
                raw_summary="Major vulnerability acquisition breach announcement and patch release.",
                engagement_score=400.0
            )
        ]

        shortlist = ranking.rank_and_shortlist(items, max_total=10)
        self.assertEqual(len(shortlist), 2)
        # The CVE item with keywords and multiple sources should rank first
        self.assertEqual(shortlist[0].id, "2")
        self.assertGreater(shortlist[0].pre_score, shortlist[1].pre_score)

    def test_ranking_max_per_source_cap(self):
        items = [
            ConsolidatedItem(
                id=str(i),
                title=f"Hacker News Story #{i}",
                url=f"https://news.ycombinator.com/item?id={i}",
                sources=["Hacker News"],
                published_at="2026-07-23T10:00:00Z",
                raw_summary="HN story summary",
                engagement_score=100.0 + i
            )
            for i in range(10)
        ]

        shortlist = ranking.rank_and_shortlist(items, max_total=10, max_per_source=3)
        self.assertEqual(len(shortlist), 3)


if __name__ == "__main__":
    unittest.main()
