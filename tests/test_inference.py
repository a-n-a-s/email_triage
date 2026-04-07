"""
Test Suite for Email Triage Inference.

Tests for:
- EmailTriageAgent prompt building
- EmailTriageAgent response parsing
- EnvClient HTTP operations
- Token usage tracking
- Retry logic
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

try:
    from inference import (
        AsyncEmailTriageAgent,
        EnvClient,
        TokenUsage,
        EpisodeResult,
        MODEL_PRICES,
        run_episode,
    )
except ImportError:
    from inference import (
        AsyncEmailTriageAgent,
        EnvClient,
        TokenUsage,
        EpisodeResult,
        MODEL_PRICES,
        run_episode,
    )


# ============================================================================
# TOKEN USAGE TESTS
# ============================================================================

class TestTokenUsage:
    """Tests for TokenUsage tracking."""

    def test_initial_token_usage(self):
        """Test initial token usage is zero."""
        tokens = TokenUsage()
        
        assert tokens.input_tokens == 0
        assert tokens.output_tokens == 0
        assert tokens.total_tokens == 0
        assert tokens.cost_usd == 0.0

    def test_add_tokens_free_model(self):
        """Test adding tokens for free model."""
        tokens = TokenUsage()
        tokens.add(100, 200, "meta-llama/Meta-Llama-3-70B-Instruct")
        
        assert tokens.input_tokens == 100
        assert tokens.output_tokens == 200
        assert tokens.total_tokens == 300
        assert tokens.cost_usd == 0.0  # Free tier

    def test_add_tokens_paid_model(self):
        """Test adding tokens for paid model."""
        tokens = TokenUsage()
        tokens.add(1000000, 500000, "gpt-4")  # 1M input, 0.5M output
        
        assert tokens.input_tokens == 1000000
        assert tokens.output_tokens == 500000
        assert tokens.total_tokens == 1500000
        # gpt-4: $30/1M input, $60/1M output
        expected_cost = (1000000 * 30.0 + 500000 * 60.0) / 1_000_000
        assert tokens.cost_usd == expected_cost

    def test_multiple_additions(self):
        """Test multiple token additions accumulate."""
        tokens = TokenUsage()
        tokens.add(100, 200)
        tokens.add(300, 400)
        
        assert tokens.input_tokens == 400
        assert tokens.output_tokens == 600
        assert tokens.total_tokens == 1000

    def test_to_dict(self):
        """Test conversion to dictionary."""
        tokens = TokenUsage(input_tokens=100, output_tokens=200, total_tokens=300, cost_usd=0.5)
        result = tokens.to_dict()
        
        assert result == {
            "input_tokens": 100,
            "output_tokens": 200,
            "total_tokens": 300,
            "cost_usd": 0.5
        }


# ============================================================================
# EPISODE RESULT TESTS
# ============================================================================

class TestEpisodeResult:
    """Tests for EpisodeResult data class."""

    def test_initial_episode_result(self):
        """Test initial episode result."""
        result = EpisodeResult(
            episode_num=0,
            timestamp="2024-01-01T00:00:00",
            model="test-model"
        )
        
        assert result.episode_num == 0
        assert result.model == "test-model"
        assert result.tasks == []
        assert result.total_reward == 0.0
        assert result.steps == 0
        assert result.success == False
        assert result.average_score == 0.0

    def test_episode_result_to_dict(self):
        """Test conversion to dictionary."""
        result = EpisodeResult(
            episode_num=1,
            timestamp="2024-01-01T00:00:00",
            model="test-model",
            total_reward=2.5,
            steps=3,
            success=True,
            average_score=0.833
        )
        result_dict = result.to_dict()
        
        assert result_dict["episode_num"] == 1
        assert result_dict["total_reward"] == 2.5
        assert result_dict["steps"] == 3
        assert result_dict["success"] == True
        assert "tokens" in result_dict


# ============================================================================
# AGENT PROMPT BUILDING TESTS
# ============================================================================

class TestAgentPromptBuilding:
    """Tests for agent prompt building."""

    def test_build_spam_classification_prompt(self):
        """Test prompt building for spam classification."""
        agent = AsyncEmailTriageAgent(
            api_base="http://test",
            api_key="test",
            model="test-model"
        )
        
        emails = [{
            "id": 0,
            "subject": "You WON $1000!",
            "sender": "prizes@scam.biz",
            "body": "Click here immediately!"
        }]
        
        prompt = agent._build_enhanced_prompt(
            task_id=1,
            task_description="Classify as spam or not spam",
            emails=emails,
            use_cot=True
        )
        
        assert "TASK: Spam Classification" in prompt
        assert "spam" in prompt
        assert "not_spam" in prompt
        assert "You WON $1000!" in prompt
        assert "reasoning" in prompt.lower()  # CoT requirement

    def test_build_ranking_prompt(self):
        """Test prompt building for urgency ranking."""
        agent = AsyncEmailTriageAgent(
            api_base="http://test",
            api_key="test",
            model="test-model"
        )
        
        emails = [
            {"id": 0, "subject": "Newsletter", "sender": "news@test.com", "body": "Weekly digest", "urgency": 3},
            {"id": 1, "subject": "Server down", "sender": "alerts@test.com", "body": "Critical!", "urgency": 1},
            {"id": 2, "subject": "Invoice due", "sender": "billing@test.com", "body": "Payment due", "urgency": 2},
        ]
        
        prompt = agent._build_enhanced_prompt(
            task_id=2,
            task_description="Rank by urgency",
            emails=emails,
            use_cot=True
        )
        
        assert "TASK: Urgency Ranking" in prompt
        assert "ranking" in prompt
        assert "most urgent" in prompt.lower()
        assert "least urgent" in prompt.lower()

    def test_build_reply_prompt(self):
        """Test prompt building for action & reply."""
        agent = AsyncEmailTriageAgent(
            api_base="http://test",
            api_key="test",
            model="test-model"
        )
        
        emails = [{
            "id": 0,
            "subject": "Project deadline",
            "sender": "client@company.com",
            "body": "Can you confirm delivery by Friday?"
        }]
        
        prompt = agent._build_enhanced_prompt(
            task_id=3,
            task_description="Action and reply",
            emails=emails,
            use_cot=True
        )
        
        assert "TASK: Action & Reply" in prompt
        assert "reply" in prompt
        assert "action_type" in prompt
        assert "reply_text" in prompt


# ============================================================================
# AGENT RESPONSE PARSING TESTS
# ============================================================================

class TestAgentResponseParsing:
    """Tests for agent response parsing."""

    def test_parse_spam_classification(self):
        """Test parsing spam classification response."""
        agent = AsyncEmailTriageAgent(
            api_base="http://test",
            api_key="test",
            model="test-model"
        )
        
        # Test valid JSON
        response = '{"label": "spam"}'
        action = agent._parse_response(response, task_id=1)
        
        assert action["task_id"] == 1
        assert action["label"] == "spam"

    def test_parse_spam_classification_case_insensitive(self):
        """Test case-insensitive label parsing."""
        agent = AsyncEmailTriageAgent(
            api_base="http://test",
            api_key="test",
            model="test-model"
        )
        
        for label in ["SPAM", "Spam", "spam", "SpAm"]:
            response = f'{{"label": "{label}"}}'
            action = agent._parse_response(response, task_id=1)
            assert action["label"] == "spam"

    def test_parse_invalid_label(self):
        """Test parsing invalid label falls back to spam."""
        agent = AsyncEmailTriageAgent(
            api_base="http://test",
            api_key="test",
            model="test-model"
        )
        
        response = '{"label": "invalid"}'
        action = agent._parse_response(response, task_id=1)
        
        assert action["label"] == "spam"

    def test_parse_ranking(self):
        """Test parsing ranking response."""
        agent = AsyncEmailTriageAgent(
            api_base="http://test",
            api_key="test",
            model="test-model"
        )
        
        response = '{"ranking": [1, 2, 0]}'
        action = agent._parse_response(response, task_id=2)
        
        assert action["task_id"] == 2
        assert action["ranking"] == [1, 2, 0]

    def test_parse_invalid_ranking_length(self):
        """Test parsing invalid ranking length falls back to default."""
        agent = AsyncEmailTriageAgent(
            api_base="http://test",
            api_key="test",
            model="test-model"
        )
        
        response = '{"ranking": [0, 1]}'  # Only 2 items
        action = agent._parse_response(response, task_id=2)
        
        assert action["ranking"] == [1, 2, 0]  # Default

    def test_parse_action_reply(self):
        """Test parsing action & reply response."""
        agent = AsyncEmailTriageAgent(
            api_base="http://test",
            api_key="test",
            model="test-model"
        )
        
        response = '{"action_type": "reply", "reply_text": "Thank you for your email."}'
        action = agent._parse_response(response, task_id=3)
        
        assert action["task_id"] == 3
        assert action["action_type"] == "reply"
        assert "Thank you" in action["reply_text"]

    def test_parse_json_in_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        agent = AsyncEmailTriageAgent(
            api_base="http://test",
            api_key="test",
            model="test-model"
        )
        
        response = '''```json
{"label": "spam"}
```'''
        action = agent._parse_response(response, task_id=1)
        
        assert action["label"] == "spam"

    def test_parse_malformed_json(self):
        """Test parsing malformed JSON falls back to default."""
        agent = AsyncEmailTriageAgent(
            api_base="http://test",
            api_key="test",
            model="test-model"
        )
        
        response = '{"label": "spam"'  # Missing closing brace
        action = agent._parse_response(response, task_id=1)
        
        assert action["label"] == "spam"  # Default fallback


# ============================================================================
# ENV CLIENT TESTS
# ============================================================================

class TestEnvClient:
    """Tests for environment HTTP client."""

    def test_env_client_initialization(self):
        """Test environment client initialization."""
        client = EnvClient(base_url="http://localhost:8000", timeout=30)
        
        assert client.base_url == "http://localhost:8000"
        assert client.timeout == 30

    @patch('inference.requests.Session')
    def test_reset(self, mock_session_class):
        """Test environment reset."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"observation": {"task_id": 1}}
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_response
        
        client = EnvClient(base_url="http://localhost:8000")
        result = client.reset()
        
        assert result == {"observation": {"task_id": 1}}
        mock_session.post.assert_called_once()

    @patch('inference.requests.Session')
    def test_step(self, mock_session_class):
        """Test environment step."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"reward": 1.0, "done": False}
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_response
        
        client = EnvClient(base_url="http://localhost:8000")
        result = client.step({"action": "test"})
        
        assert result == {"reward": 1.0, "done": False}

    @patch('inference.requests.Session')
    def test_health(self, mock_session_class):
        """Test environment health check."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        
        client = EnvClient(base_url="http://localhost:8000")
        result = client.health()
        
        assert result == {"status": "healthy"}


# ============================================================================
# MODEL PRICING TESTS
# ============================================================================

class TestModelPricing:
    """Tests for model pricing configuration."""

    def test_model_prices_exist(self):
        """Test that model prices are defined."""
        assert len(MODEL_PRICES) > 0
        assert "default" in MODEL_PRICES

    def test_model_price_structure(self):
        """Test model price structure."""
        for model, prices in MODEL_PRICES.items():
            assert "input" in prices
            assert "output" in prices
            assert isinstance(prices["input"], (int, float))
            assert isinstance(prices["output"], (int, float))
            assert prices["input"] >= 0
            assert prices["output"] >= 0

    def test_popular_models_priced(self):
        """Test that popular models have pricing."""
        popular_models = [
            "gpt-4",
            "gpt-3.5-turbo",
            "claude-3-opus",
            "meta-llama/Meta-Llama-3-70B-Instruct"
        ]
        
        for model in popular_models:
            assert model in MODEL_PRICES


# ============================================================================
# FEW-SHOT EXAMPLES TESTS
# ============================================================================

class TestFewShotExamples:
    """Tests for few-shot learning examples."""

    def test_few_shot_examples_exist(self):
        """Test that few-shot examples are defined."""
        examples = AsyncEmailTriageAgent.FEW_SHOT_EXAMPLES
        
        assert 1 in examples  # Task 1
        assert 2 in examples  # Task 2
        assert 3 in examples  # Task 3

    def test_few_shot_examples_structure(self):
        """Test few-shot examples structure."""
        examples = AsyncEmailTriageAgent.FEW_SHOT_EXAMPLES
        
        # Task 1 examples should have label and reasoning
        for ex in examples[1]:
            assert "label" in ex
            assert "reasoning" in ex
        
        # Task 2 examples should have ranking and reasoning
        for ex in examples[2]:
            assert "ranking" in ex
            assert "reasoning" in ex
        
        # Task 3 examples should have action_type, reply_text, and reasoning
        for ex in examples[3]:
            assert "action_type" in ex
            assert "reply_text" in ex
            assert "reasoning" in ex


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
