from __future__ import annotations

import math
import os
import re
from functools import lru_cache


class SemanticRelevanceService:
    MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    POSITIVE_PROTOTYPES = {
        "ai_builder_tools": (
            "AI builder tools, developer tooling for LLM apps, agent frameworks, "
            "inference tooling, evaluation tooling, prompt workflows, AI copilots."
        ),
        "agentic_workflows": (
            "LLM agents, autonomous workflows, multi-step orchestration, function calling, "
            "tool use, agent execution, planning systems."
        ),
        "rag_systems": (
            "retrieval augmented generation, vector databases, search pipelines, reranking, "
            "embeddings, knowledge retrieval for AI applications."
        ),
        "model_platforms": (
            "model APIs, inference providers, fine tuning platforms, model hosting, "
            "SDK updates, AI platform releases, model product launches."
        ),
        "ai_product_launches": (
            "AI product launch, model release, API update, assistant product, "
            "developer platform release, AI startup launch."
        ),
        "open_source_ai": (
            "open source LLM tools, agent libraries, developer frameworks, AI infrastructure, "
            "RAG toolkits, local model tooling."
        ),
    }
    NEGATIVE_PROTOTYPES = {
        "general_tech": (
            "general programming story, personal blog post, infrastructure unrelated to AI, "
            "software career advice, generic startup essay, unrelated tech opinion."
        ),
        "non_ai_discussion": (
            "web development discussion, operating systems story, programming anecdote, "
            "management essay, unrelated engineering post."
        ),
    }
    SOURCE_PRIORS = {
        "OpenAI": 0.55,
        "Anthropic": 0.55,
        "Replicate": 0.45,
        "Vercel": 0.35,
        "HuggingFace": 0.45,
        "GitHub": 0.3,
        "ProductHunt": 0.25,
        "Reddit": 0.15,
        "HackerNews": 0.1,
        "Lobsters": 0.1,
        "TechCrunch": 0.2,
    }
    NEGATIVE_PHRASES = {
        "career advice",
        "interview with",
        "programming interview",
        "programming",
        "manager",
        "management",
        "operating systems",
        "linux kernel",
        "startup founder story",
        "salary",
        "interview prep",
        "personal blog",
        "browser engine",
        "javascript framework",
    }

    _tokenizer = None
    _model = None
    _transformer_ready = None
    _prototype_cache = None

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9\-\+\.]+", SemanticRelevanceService._normalize(text))

    @staticmethod
    def _hashed_embedding(text: str, size: int = 256) -> list[float]:
        vector = [0.0] * size
        tokens = SemanticRelevanceService._tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            idx = hash(token) % size
            vector[idx] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    @staticmethod
    def _cosine(vec_a: list[float], vec_b: list[float]) -> float:
        if not vec_a or not vec_b:
            return 0.0
        return sum(a * b for a, b in zip(vec_a, vec_b))

    @staticmethod
    def _ensure_transformer():
        if SemanticRelevanceService._transformer_ready is not None:
            return SemanticRelevanceService._transformer_ready
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            SemanticRelevanceService._tokenizer = AutoTokenizer.from_pretrained(
                SemanticRelevanceService.MODEL_NAME
            )
            SemanticRelevanceService._model = AutoModel.from_pretrained(
                SemanticRelevanceService.MODEL_NAME
            )
            SemanticRelevanceService._model.eval()
            SemanticRelevanceService._transformer_ready = (torch, True)
        except Exception:
            SemanticRelevanceService._tokenizer = None
            SemanticRelevanceService._model = None
            SemanticRelevanceService._transformer_ready = (None, False)
        return SemanticRelevanceService._transformer_ready

    @staticmethod
    @lru_cache(maxsize=512)
    def _encode_text(text: str) -> tuple[float, ...]:
        torch, transformer_ready = SemanticRelevanceService._ensure_transformer()
        normalized = SemanticRelevanceService._normalize(text)
        if not normalized:
            return tuple()

        if not transformer_ready:
            return tuple(SemanticRelevanceService._hashed_embedding(normalized))

        tokenizer = SemanticRelevanceService._tokenizer
        model = SemanticRelevanceService._model
        inputs = tokenizer(
            normalized,
            truncation=True,
            max_length=256,
            padding=True,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = model(**inputs)
            token_embeddings = outputs.last_hidden_state
            attention_mask = inputs["attention_mask"].unsqueeze(-1).expand(token_embeddings.size()).float()
            summed = (token_embeddings * attention_mask).sum(dim=1)
            counts = attention_mask.sum(dim=1).clamp(min=1e-9)
            mean_pooled = summed / counts
            normalized_vec = torch.nn.functional.normalize(mean_pooled, p=2, dim=1)
        return tuple(normalized_vec[0].cpu().tolist())

    @staticmethod
    def _build_prototype_cache():
        if SemanticRelevanceService._prototype_cache is not None:
            return SemanticRelevanceService._prototype_cache
        cache = {
            "positive": {
                label: SemanticRelevanceService._encode_text(text)
                for label, text in SemanticRelevanceService.POSITIVE_PROTOTYPES.items()
            },
            "negative": {
                label: SemanticRelevanceService._encode_text(text)
                for label, text in SemanticRelevanceService.NEGATIVE_PROTOTYPES.items()
            },
        }
        SemanticRelevanceService._prototype_cache = cache
        return cache

    @staticmethod
    def score_text(text: str, source: str) -> dict[str, float | str]:
        normalized = SemanticRelevanceService._normalize(text)
        embedding = list(SemanticRelevanceService._encode_text(normalized))
        prototypes = SemanticRelevanceService._build_prototype_cache()

        positive_scores = {
            label: SemanticRelevanceService._cosine(embedding, list(vector))
            for label, vector in prototypes["positive"].items()
        }
        negative_scores = {
            label: SemanticRelevanceService._cosine(embedding, list(vector))
            for label, vector in prototypes["negative"].items()
        }

        best_positive_label = max(positive_scores, key=positive_scores.get, default="ai_builder_tools")
        best_negative = max(negative_scores.values(), default=0.0)
        negative_penalty = 0.0
        if any(phrase in normalized for phrase in SemanticRelevanceService.NEGATIVE_PHRASES):
            negative_penalty += 0.2

        semantic_similarity = max(positive_scores.values(), default=0.0)
        source_prior = SemanticRelevanceService.SOURCE_PRIORS.get(source, 0.0)
        builder_relevance = max(
            (semantic_similarity * 3.2) + source_prior - (best_negative * 1.2) - negative_penalty,
            0.0,
        )

        return {
            "builder_relevance_score": round(builder_relevance, 3),
            "semantic_similarity": round(semantic_similarity, 3),
            "negative_similarity": round(best_negative + negative_penalty, 3),
            "prototype_label": best_positive_label,
        }
