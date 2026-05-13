import unittest
from unittest.mock import patch

class RateLimitFallbackTest(unittest.TestCase):
    def test_rate_limit_fallback(self):
        import bot_curriculo.modules.job_analyzer as ja
        with patch.object(ja, "_call_gemini", return_value="__RATE_LIMIT__"):
            from bot_curriculo.modules.resume_adapter import adapt_resume_and_analyze
            resume_text = "Este é um currículo de teste"
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
