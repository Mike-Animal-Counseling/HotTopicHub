from app.services.ai_enrichment_service import AIEnrichmentService


def test_parse_json_block_accepts_plain_json():
    payload = AIEnrichmentService._parse_json_block(
        """
        {
          "summary": "A concise summary.",
          "key_insights": "A factual insight.",
          "why_it_matters": "A clear reason.",
          "technical_summary": "A technical takeaway."
        }
        """
    )

    assert payload == {
        "summary": "A concise summary.",
        "key_insights": "A factual insight.",
        "why_it_matters": "A clear reason.",
        "technical_summary": "A technical takeaway.",
    }


def test_parse_json_block_accepts_fenced_json():
    payload = AIEnrichmentService._parse_json_block(
        """```json
        {
          "summary": "Summary.",
          "key_insights": "Insight.",
          "why_it_matters": "Why.",
          "technical_summary": "Technical."
        }
        ```"""
    )

    assert payload == {
        "summary": "Summary.",
        "key_insights": "Insight.",
        "why_it_matters": "Why.",
        "technical_summary": "Technical.",
    }
