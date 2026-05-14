import unittest
from unittest.mock import patch


class RateLimitFallbackTest(unittest.TestCase):
    def test_rate_limit_fallback(self):
        import app.core.analyzer as analyzer
        with patch.object(analyzer, "_call_gemini", return_value="__RATE_LIMIT__"):
            from app.core.resume import adapt_resume_and_analyze
            resume_text = "Este e um curriculo de teste"
            job = {
                "titulo": "Desenvolvedor Python",
                "empresa": "Empresa de Teste",
                "local": "Brasil",
                "descricao": "",
            }
            adapted, analysis = adapt_resume_and_analyze(resume_text, job)
            self.assertIsInstance(adapted, dict)
            self.assertTrue(adapted.get("_rate_limit_fallback"))


if __name__ == "__main__":
    unittest.main()
