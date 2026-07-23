import json
import unittest
from unittest.mock import patch, MagicMock
from app.models import ConsolidatedItem, ProcessedItem
from app.services import llm

class TestLLMBatching(unittest.TestCase):

    @patch("app.services.llm._call_gemini_api")
    def test_batch_summarize_items_success(self, mock_call):
        items = [
            ConsolidatedItem(
                id="1",
                title="OpenAI Releases New Model",
                url="https://openai.com/1",
                sources=["OpenAI Blog"],
                published_at="2026-07-23T10:00:00Z",
                raw_summary="OpenAI announces a breakthrough model.",
                engagement_score=100.0,
                category_hint="Artificial Intelligence"
            ),
            ConsolidatedItem(
                id="2",
                title="GitHub Announces New Feature",
                url="https://github.com/2",
                sources=["GitHub Trending"],
                published_at="2026-07-23T10:00:00Z",
                raw_summary="GitHub adds new developer workflow automation.",
                engagement_score=50.0,
                category_hint="Developer Tools"
            )
        ]

        mock_json_array = json.dumps([
            {
                "headline": "OpenAI Unveils New AI Model",
                "summary": "OpenAI announced a powerful new model today.",
                "why_it_matters": "Major advancement in generative AI capabilities.",
                "developer_impact": "Developers can integrate via API.",
                "importance": "Critical",
                "category": "Artificial Intelligence"
            },
            {
                "headline": "GitHub Adds Workflow Automation",
                "summary": "GitHub introduces automated workflow improvements.",
                "why_it_matters": "Enhances developer productivity.",
                "developer_impact": "Actions pipelines get faster execution.",
                "importance": "High",
                "category": "Developer Tools"
            }
        ])

        mock_call.return_value = (f"```json\n{mock_json_array}\n```", "success")

        results = llm.batch_summarize_items(items, batch_size=5)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].headline, "OpenAI Unveils New AI Model")
        self.assertEqual(results[0].category, "Artificial Intelligence")
        self.assertEqual(results[0].importance, "Critical")
        self.assertEqual(results[1].headline, "GitHub Adds Workflow Automation")
        self.assertEqual(results[1].category, "Developer Tools")

    @patch("app.services.llm._call_gemini_api")
    def test_batch_summarize_items_mismatch_fallback(self, mock_call):
        items = [
            ConsolidatedItem(
                id="1",
                title="Story 1",
                url="https://example.com/1",
                sources=["Blog"],
                published_at="2026-07-23T10:00:00Z",
                raw_summary="Summary 1",
                engagement_score=10.0
            ),
            ConsolidatedItem(
                id="2",
                title="Story 2",
                url="https://example.com/2",
                sources=["Blog"],
                published_at="2026-07-23T10:00:00Z",
                raw_summary="Summary 2",
                engagement_score=10.0
            )
        ]

        # Return list with length 1 (mismatch) for batch, then per-item calls succeed
        mock_call.side_effect = [
            ("```json\n[{\"headline\": \"Only One Item\"}]\n```", "success"),
            ("```json\n{\"headline\": \"Story 1 Headline\", \"summary\": \"s1\", \"why_it_matters\": \"w1\", \"developer_impact\": \"d1\", \"importance\": \"Medium\", \"category\": \"General Developer Buzz\"}\n```", "success"),
            ("```json\n{\"headline\": \"Story 2 Headline\", \"summary\": \"s2\", \"why_it_matters\": \"w2\", \"developer_impact\": \"d2\", \"importance\": \"Medium\", \"category\": \"General Developer Buzz\"}\n```", "success")
        ]

        results = llm.batch_summarize_items(items, batch_size=5)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].headline, "Story 1 Headline")
        self.assertEqual(results[1].headline, "Story 2 Headline")

    def test_clean_json_response_array_and_object(self):
        obj_str = "Here is JSON:\n```json\n{\"headline\": \"test\"}\n```"
        arr_str = "Here is JSON Array:\n```json\n[{\"headline\": \"test\"}]\n```"
        self.assertEqual(llm._clean_json_response(obj_str), '{"headline": "test"}')
        self.assertEqual(llm._clean_json_response(arr_str), '[{"headline": "test"}]')


if __name__ == "__main__":
    unittest.main()
