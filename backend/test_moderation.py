#!/usr/bin/env python3
"""
Test script for the Detoxify-based moderation system.
Tests various comment types to validate the ML-based moderation.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime

from app.models import Base, Topic, Comment, DailyTopicBatch
from app.services.moderation_service import ModerationService

# Setup test database (in-memory SQLite)
engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

# Create a test topic
db = SessionLocal()
batch = DailyTopicBatch(date="2026-03-09")
db.add(batch)
db.commit()

test_topic = Topic(
    title="Test Topic",
    summary="Test Summary",
    batch_id=batch.id,
    date_key="2026-03-09",
    published_time=datetime.now(),
)
db.add(test_topic)
db.commit()
topic_id = test_topic.id
db.close()

# Test cases
test_comments = [
    {
        "text": "This is a great article! Really useful information.",
        "expected": "approved",
        "description": "Normal positive comment",
    },
    {
        "text": "I completely disagree with this opinion.",
        "expected": "approved",
        "description": "Disagreement but respectful",
    },
    {
        "text": "You're an idiot and I hate you",
        "expected": "pending_review or rejected",
        "description": "Toxic content with hate",
    },
    {
        "text": "This is stupid and dumb.",
        "expected": "pending_review or rejected",
        "description": "Mild profanity",
    },
    {
        "text": "I want to to harm people who disagree with me and want to kill me.",
        "expected": "pending_review or rejected",
        "description": "Threat/violence related",
    },
    {
        "text": "Really loved this!\nCan't wait for the next one.",
        "expected": "approved",
        "description": "Positive multi-line comment",
    },
    {
        "text": "bit.ly/malicious http://bit.ly/spam http://bit.ly/bad",
        "expected": "pending_review or rejected",
        "description": "Too many shortener links",
    },
    {
        "text": "Interesting perspective on AI trends.",
        "expected": "approved",
        "description": "Technical discussion",
    },
    {
        "text": "Wow, I hate this and want to hurt people!",
        "expected": "pending_review or rejected",
        "description": "High toxicity - threat + hate",
    },
    {
        "text": "hello, how are you?",
        "expected": "Approved",
        "description": "Friendly greeting",
    },
]

print("=" * 80)
print("Testing Detoxify-based Moderation System")
print("=" * 80)

db = SessionLocal()
for i, test_case in enumerate(test_comments, 1):
    text = test_case["text"]
    description = test_case["description"]
    expected = test_case["expected"]

    # Run moderation
    result = ModerationService.run_auto_moderation(
        db=db,
        topic_id=topic_id,
        user_identifier=f"test_user_{i}",
        text=text,
        image_url=None,
    )

    # Get toxicity score for display
    toxicity_score, _ = ModerationService._check_toxicity(text)

    print(f"\nTest {i}: {description}")
    print(f"  Text: {text[:60]}{'...' if len(text) > 60 else ''}")
    print(f"  Toxicity Score: {toxicity_score:.4f}")
    print(f"  Expected: {expected}")
    print(f"  Result: {result['status'].upper()}")
    print(f"  Flags: {', '.join(result['flags']) if result['flags'] else 'none'}")
    print(f"  Reason: {result['reason']}")

db.close()
print("\n" + "=" * 80)
print("Test Complete!")
print("=" * 80)
