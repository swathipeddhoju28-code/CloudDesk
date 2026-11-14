import json
import logging
import os
import unittest
from io import StringIO
from unittest.mock import patch

from backend.app.core.config import Settings
from backend.app.core.logging import log_context, setup_logging


class SettingsTests(unittest.TestCase):
    def test_offline_defaults(self) -> None:
        settings = Settings(_env_file=None)

        self.assertTrue(settings.demo_mode)
        self.assertEqual(settings.llm_provider, "fake")
        self.assertEqual(settings.vector_store, "memory")
        self.assertEqual(settings.embedding_dimensions, 384)
        self.assertEqual(settings.database_url, "sqlite+aiosqlite:///./data/support.db")

    def test_environment_overrides_and_secrets_are_redacted(self) -> None:
        environment = {
            "DEMO_MODE": "false",
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "example-model",
            "CORS_ORIGINS": '["https://console.example.test"]',
            "LLM_API_KEY": "do-not-print",
            "DATABASE_URL": "postgresql+asyncpg://user:db-password@db.example.test/app",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings(_env_file=None)

        self.assertFalse(settings.demo_mode)
        self.assertEqual(settings.llm_provider, "openai")
        self.assertEqual(settings.llm_model, "example-model")
        self.assertEqual(settings.cors_origins, ["https://console.example.test"])
        self.assertEqual(
            settings.model_dump()["llm_api_key"],
            "**********",
        )
        self.assertEqual(
            settings.model_dump()["database_url"],
            "postgresql+asyncpg://user:**********@db.example.test/app",
        )
        self.assertNotIn("do-not-print", str(settings.model_dump()))
        self.assertNotIn("db-password", str(settings.model_dump()))

    def test_supabase_secret_takes_precedence_for_jwt(self) -> None:
        settings = Settings(
            _env_file=None,
            jwt_secret="local-secret",
            supabase_jwt_secret="supabase-secret",
        )

        self.assertEqual(settings.effective_jwt_secret, "supabase-secret")


class JsonLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        root_logger = logging.getLogger()
        self.original_handlers = root_logger.handlers[:]
        self.original_level = root_logger.level

    def tearDown(self) -> None:
        root_logger = logging.getLogger()
        root_logger.handlers[:] = self.original_handlers
        root_logger.setLevel(self.original_level)

    def test_json_output_has_context_and_null_defaults(self) -> None:
        stream = StringIO()
        setup_logging(level="DEBUG", stream=stream)
        logger = logging.getLogger("clouddesk.test")

        with log_context(request_id="request-123"):
            with log_context(workflow_id="workflow-456"):
                logger.info("Started %s", "workflow")
            logger.info("Request complete")
        logger.info("Outside request")

        records = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(records[0]["message"], "Started workflow")
        self.assertEqual(records[0]["request_id"], "request-123")
        self.assertEqual(records[0]["workflow_id"], "workflow-456")
        self.assertEqual(records[1]["request_id"], "request-123")
        self.assertIsNone(records[1]["workflow_id"])
        self.assertIsNone(records[2]["request_id"])
        self.assertIsNone(records[2]["workflow_id"])
        self.assertEqual(records[0]["level"], "INFO")

    def test_invalid_level_is_reported(self) -> None:
        with self.assertRaises(ValueError):
            setup_logging(level="not-a-level")


if __name__ == "__main__":
    unittest.main()
