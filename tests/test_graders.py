"""
Test Suite for Email Triage Environment Graders.

Tests for:
- Task 1: Spam classification grader
- Task 2: Urgency ranking grader
- Task 3: Action + reply grader
"""

import pytest
from server.email_triage_environment import (
    grade_task1,
    grade_task2,
    grade_task3,
    EmailTemplates,
)
from models import EmailTriageAction


# ============================================================================
# TASK 1: SPAM CLASSIFICATION TESTS
# ============================================================================

class TestGradeTask1:
    """Tests for spam classification grader."""

    def test_correct_spam_classification(self):
        """Test correct classification of spam email."""
        email = {"correct_label": "spam"}
        action = EmailTriageAction(task_id=1, label="spam")
        
        score, feedback = grade_task1(action, email, step_count=2)
        
        assert score == 1.0
        assert "Correct" in feedback
        assert "'spam'" in feedback

    def test_correct_not_spam_classification(self):
        """Test correct classification of not-spam email."""
        email = {"correct_label": "not_spam"}
        action = EmailTriageAction(task_id=1, label="not_spam")
        
        score, feedback = grade_task1(action, email, step_count=2)
        
        assert score == 1.0
        assert "Correct" in feedback

    def test_wrong_classification(self):
        """Test wrong classification."""
        email = {"correct_label": "spam"}
        action = EmailTriageAction(task_id=1, label="not_spam")
        
        score, feedback = grade_task1(action, email, step_count=2)
        
        assert score == 0.0
        assert "Wrong" in feedback
        assert "Expected 'spam'" in feedback

    def test_efficiency_bonus(self):
        """Test first-try efficiency bonus."""
        email = {"correct_label": "spam"}
        action = EmailTriageAction(task_id=1, label="spam")
        
        score, feedback = grade_task1(action, email, step_count=1)
        
        assert score == 1.0  # Capped at 1.0
        assert "efficiency bonus" in feedback

    def test_invalid_label(self):
        """Test invalid label input."""
        email = {"correct_label": "spam"}
        action = EmailTriageAction(task_id=1, label="invalid")
        
        score, feedback = grade_task1(action, email, step_count=2)
        
        assert score == -0.2
        assert "Invalid label" in feedback
        assert "spam" in feedback
        assert "not_spam" in feedback

    def test_case_insensitive(self):
        """Test that classification is case-insensitive."""
        email = {"correct_label": "spam"}
        
        for label in ["spam", "SPAM", "Spam", "SpAm"]:
            action = EmailTriageAction(task_id=1, label=label)
            score, feedback = grade_task1(action, email, step_count=2)
            assert score == 1.0, f"Failed for label: {label}"

    def test_whitespace_handling(self):
        """Test that whitespace is handled correctly."""
        email = {"correct_label": "spam"}
        action = EmailTriageAction(task_id=1, label="  spam  \n")
        
        score, feedback = grade_task1(action, email, step_count=2)
        
        assert score == 1.0


# ============================================================================
# TASK 2: URGENCY RANKING TESTS
# ============================================================================

class TestGradeTask2:
    """Tests for urgency ranking grader."""

    def test_perfect_ranking(self):
        """Test perfect ranking (3/3 correct)."""
        action = EmailTriageAction(task_id=2, ranking=[1, 2, 0])
        correct_order = [1, 2, 0]
        
        score, feedback = grade_task2(action, correct_order)
        
        assert score == 1.0
        assert "Perfect" in feedback

    def test_partial_ranking_2_correct(self):
        """Test ranking with 2/3 correct positions."""
        # Note: With permutations of [0,1,2], it's impossible to get exactly 2 matches
        # If 2 positions are correct, the 3rd must also be correct (only 1 value remains)
        # So we test the closest case: 1 match (which scores 0.3)
        action = EmailTriageAction(task_id=2, ranking=[1, 0, 2])
        correct_order = [1, 2, 0]
        
        score, feedback = grade_task2(action, correct_order)
        
        # [1,0,2] vs [1,2,0]: only position 0 matches
        assert score == 0.3
        assert "1/3" in feedback

    def test_partial_ranking_all_wrong(self):
        """Test ranking with 0/3 correct (complete permutation)."""
        # [2, 0, 1] vs [1, 2, 0]: no positions match
        action = EmailTriageAction(task_id=2, ranking=[2, 0, 1])
        correct_order = [1, 2, 0]
        
        score, feedback = grade_task2(action, correct_order)
        
        assert score == 0.0
        assert "Incorrect" in feedback

    def test_partial_ranking_1_correct(self):
        """Test ranking with 1/3 correct."""
        # Let's find a case with exactly 1 match
        # correct_order = [1, 2, 0]
        # [0, 2, 1]: pos 0 (0!=1), pos 1 (2==2) match!, pos 2 (1!=0)
        action = EmailTriageAction(task_id=2, ranking=[0, 2, 1])
        correct_order = [1, 2, 0]
        
        score, feedback = grade_task2(action, correct_order)
        
        assert score == 0.3
        assert "1/3" in feedback

    def test_wrong_ranking(self):
        """Test completely wrong ranking."""
        action = EmailTriageAction(task_id=2, ranking=[0, 1, 2])
        correct_order = [2, 1, 0]
        
        score, feedback = grade_task2(action, correct_order)
        
        # Position 1 matches (value 1)
        assert score <= 0.3

    def test_invalid_ranking_length(self):
        """Test ranking with wrong length."""
        action = EmailTriageAction(task_id=2, ranking=[0, 1])
        correct_order = [1, 2, 0]
        
        score, feedback = grade_task2(action, correct_order)
        
        assert score == -0.2
        assert "Invalid ranking length" in feedback

    def test_invalid_ranking_values(self):
        """Test ranking with invalid values."""
        action = EmailTriageAction(task_id=2, ranking=[0, 1, 3])
        correct_order = [1, 2, 0]
        
        score, feedback = grade_task2(action, correct_order)
        
        assert score == -0.2
        assert "must contain exactly" in feedback

    def test_empty_ranking(self):
        """Test empty ranking."""
        action = EmailTriageAction(task_id=2, ranking=[])
        correct_order = [1, 2, 0]
        
        score, feedback = grade_task2(action, correct_order)
        
        assert score == -0.2
        assert "Invalid ranking" in feedback

    def test_none_ranking(self):
        """Test None ranking."""
        action = EmailTriageAction(task_id=2, ranking=None)
        correct_order = [1, 2, 0]
        
        score, feedback = grade_task2(action, correct_order)
        
        assert score == -0.2


# ============================================================================
# TASK 3: ACTION + REPLY TESTS
# ============================================================================

class TestGradeTask3:
    """Tests for action + reply grader."""

    def test_correct_action_with_reply(self):
        """Test correct action with good reply."""
        action = EmailTriageAction(
            task_id=3,
            action_type="reply",
            reply_text="I confirm we will deliver by Friday. The deadline is noted."
        )
        correct_action = "reply"
        required_keywords = ["confirm", "friday", "deadline", "deliver"]
        
        score, feedback = grade_task3(action, required_keywords, correct_action)
        
        assert score >= 0.9  # Correct action (0.5) + all keywords (0.5)
        assert "Excellent" in feedback or "Good" in feedback

    def test_correct_action_no_keywords(self):
        """Test correct action with no keywords in reply."""
        action = EmailTriageAction(
            task_id=3,
            action_type="reply",
            reply_text="Hello there, thanks for your message."
        )
        correct_action = "reply"
        required_keywords = ["confirm", "friday", "deadline"]
        
        score, feedback = grade_task3(action, required_keywords, correct_action)
        
        assert score == 0.5  # Correct action only
        assert "0/3" in feedback or "correct action" in feedback

    def test_wrong_action(self):
        """Test wrong action type."""
        action = EmailTriageAction(
            task_id=3,
            action_type="archive",
            reply_text=""
        )
        correct_action = "reply"
        required_keywords = []
        
        score, feedback = grade_task3(action, required_keywords, correct_action)
        
        assert score < 0.5
        assert "wrong action" in feedback

    def test_invalid_action_type(self):
        """Test invalid action type."""
        action = EmailTriageAction(
            task_id=3,
            action_type="invalid",
            reply_text=""
        )
        correct_action = "reply"
        required_keywords = []
        
        score, feedback = grade_task3(action, required_keywords, correct_action)
        
        assert score == -0.2
        assert "Invalid action" in feedback

    def test_delete_action_no_reply_needed(self):
        """Test delete action (no reply needed)."""
        action = EmailTriageAction(
            task_id=3,
            action_type="delete",
            reply_text=""
        )
        correct_action = "delete"
        required_keywords = []
        
        score, feedback = grade_task3(action, required_keywords, correct_action)
        
        assert score == 1.0

    def test_case_insensitive_action(self):
        """Test that action type is case-insensitive."""
        for action_type in ["reply", "REPLY", "Reply", "RePlY"]:
            action = EmailTriageAction(
                task_id=3,
                action_type=action_type,
                reply_text="test"
            )
            score, _ = grade_task3(action, [], "reply")
            assert score >= 0.5, f"Failed for action_type: {action_type}"

    def test_partial_keyword_coverage(self):
        """Test partial keyword coverage."""
        action = EmailTriageAction(
            task_id=3,
            action_type="reply",
            reply_text="I confirm the Friday deadline for deliverables."
        )
        correct_action = "reply"
        required_keywords = ["confirm", "friday", "deadline", "deliver", "urgent"]
        
        score, feedback = grade_task3(action, required_keywords, correct_action)
        
        # 4/5 keywords = 0.4 + 0.5 for correct action = 0.9
        assert 0.8 <= score <= 1.0


# ============================================================================
# EMAIL TEMPLATES TESTS
# ============================================================================

class TestEmailTemplates:
    """Tests for dynamic email generation."""

    def test_generate_spam_email(self):
        """Test spam email generation."""
        email = EmailTemplates.generate_spam_email()
        
        assert "id" in email
        assert "subject" in email
        assert "sender" in email
        assert "body" in email
        assert email["correct_label"] == "spam"

    def test_generate_not_spam_email(self):
        """Test not-spam email generation."""
        email = EmailTemplates.generate_not_spam_email()
        
        assert "id" in email
        assert "subject" in email
        assert email["correct_label"] == "not_spam"

    def test_generate_ranking_emails(self):
        """Test ranking email generation."""
        emails, correct_order = EmailTemplates.generate_ranking_emails()
        
        assert len(emails) == 3
        assert len(correct_order) == 3
        assert set(correct_order) == {0, 1, 2}
        
        for email in emails:
            assert "id" in email
            assert "subject" in email
            assert "urgency" in email

    def test_generate_reply_email(self):
        """Test reply email generation."""
        email, keywords = EmailTemplates.generate_reply_email()
        
        assert "id" in email
        assert "subject" in email
        assert "body" in email
        assert "correct_action" in email
        assert email["correct_action"] in ["reply", "forward", "archive", "delete"]
        assert isinstance(keywords, list)

    def test_template_filling(self):
        """Test template placeholder filling."""
        result = EmailTemplates._fill_template("Hello {name}, your amount is ${amount}.")
        
        assert "{name}" not in result
        assert "{amount}" not in result
        assert "Hello" in result

    def test_multiple_generations_different(self):
        """Test that multiple generations produce varied emails."""
        emails = [EmailTemplates.generate_spam_email() for _ in range(10)]
        subjects = [e["subject"] for e in emails]
        
        # At least some should be different
        assert len(set(subjects)) > 1


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
