import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import score_candidates


RESULT = {
    "scores": [
        {
            "id": "topic-1",
            "beginner_value": 28,
            "testability": 24,
            "one_person_business_fit": 18,
            "heat_and_timeliness": 13,
            "production_feasibility": 9,
            "total": 92,
            "reason": "适合实测",
        },
        {
            "id": "topic-2",
            "beginner_value": 20,
            "testability": 18,
            "one_person_business_fit": 15,
            "heat_and_timeliness": 5,
            "production_feasibility": 8,
            "total": 66,
            "reason": "热度证据较弱",
        },
    ]
}


class ScoreCandidatesTest(unittest.TestCase):
    def test_workbuddy_structured_output(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"structured_output": RESULT}, ensure_ascii=False),
            stderr="",
        )
        with patch.object(score_candidates.shutil, "which", return_value="codebuddy"), patch.object(
            score_candidates.subprocess, "run", return_value=completed
        ) as run:
            result = score_candidates.call_workbuddy("prompt", 10)
        self.assertEqual(result, RESULT)
        self.assertIn("--disallowedTools", run.call_args.args[0])

    def test_huawei_openai_compatible_output(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(RESULT, ensure_ascii=False)}}]
        }
        environment = {
            "HUAWEI_MAAS_ENDPOINT": "https://example.com/chat/completions",
            "HUAWEI_MAAS_MODEL": "example-model",
            "HUAWEI_MAAS_API_KEY": "test-key",
        }
        with patch.dict(os.environ, environment, clear=False), patch.object(
            score_candidates.requests, "post", return_value=response
        ):
            result = score_candidates.call_huawei("prompt", 10)
        self.assertEqual(result, RESULT)

    def test_score_validation_and_sorting(self):
        validated = score_candidates.validate_scores(RESULT, {"topic-1", "topic-2"})
        self.assertEqual([score["id"] for score in validated["scores"]], ["topic-1", "topic-2"])

    def test_incorrect_total_is_rejected(self):
        invalid = json.loads(json.dumps(RESULT))
        invalid["scores"][0]["total"] = 91
        with self.assertRaises(ValueError):
            score_candidates.validate_scores(invalid, {"topic-1", "topic-2"})


if __name__ == "__main__":
    unittest.main()
