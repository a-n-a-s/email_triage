"""
Test Suite for Email Triage Database Operations.

Tests for:
- Database initialization
- Episode saving and retrieval
- Model statistics
- Analytics queries
- Database cleanup
"""

import pytest
import sqlite3
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

try:
    from server.database import (
        init_db,
        save_episode,
        get_episode,
        get_recent_episodes,
        get_model_stats,
        get_analytics,
        clear_database,
        get_db_connection,
        DATABASE_PATH,
    )
except ImportError:
    from database import (
        init_db,
        save_episode,
        get_episode,
        get_recent_episodes,
        get_model_stats,
        get_analytics,
        clear_database,
        get_db_connection,
        DATABASE_PATH,
    )


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Initialize database
    init_db(db_path)
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def populated_db(temp_db):
    """Create a database with test data."""
    # Save test episodes
    save_episode(
        episode_id="test-episode-1",
        model_name="test-model-v1",
        model_config={"temperature": 0.2},
        total_reward=2.5,
        average_score=0.833,
        steps=3,
        completed=True,
        duration_seconds=10.5,
        tasks=[
            {"task_id": 1, "reward": 1.0, "feedback": "Correct", "action": {"label": "spam"}},
            {"task_id": 2, "reward": 0.6, "feedback": "Good", "action": {"ranking": [1, 2, 0]}},
            {"task_id": 3, "reward": 0.9, "feedback": "Excellent", "action": {"action_type": "reply"}},
        ],
        db_path=temp_db
    )
    
    save_episode(
        episode_id="test-episode-2",
        model_name="test-model-v1",
        model_config={"temperature": 0.2},
        total_reward=2.0,
        average_score=0.667,
        steps=3,
        completed=True,
        duration_seconds=12.0,
        tasks=[
            {"task_id": 1, "reward": 1.0, "feedback": "Correct", "action": {"label": "not_spam"}},
            {"task_id": 2, "reward": 0.3, "feedback": "Partial", "action": {"ranking": [0, 2, 1]}},
            {"task_id": 3, "reward": 0.7, "feedback": "Good", "action": {"action_type": "reply"}},
        ],
        db_path=temp_db
    )
    
    save_episode(
        episode_id="test-episode-3",
        model_name="test-model-v2",
        model_config={"temperature": 0.3},
        total_reward=1.5,
        average_score=0.5,
        steps=4,
        completed=False,
        duration_seconds=15.0,
        tasks=[
            {"task_id": 1, "reward": 0.0, "feedback": "Wrong", "action": {"label": "spam"}},
            {"task_id": 2, "reward": 0.6, "feedback": "Good", "action": {"ranking": [1, 0, 2]}},
        ],
        db_path=temp_db
    )
    
    yield temp_db


# ============================================================================
# DATABASE INITIALIZATION TESTS
# ============================================================================

class TestDatabaseInitialization:
    """Tests for database initialization."""

    def test_init_db_creates_tables(self, temp_db):
        """Test that init_db creates required tables."""
        with get_db_connection(temp_db) as conn:
            # Check episodes table exists
            result = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='episodes'
            """).fetchone()
            assert result is not None
            
            # Check tasks table exists
            result = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='tasks'
            """).fetchone()
            assert result is not None
            
            # Check model_performance table exists
            result = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='model_performance'
            """).fetchone()
            assert result is not None

    def test_init_db_creates_indexes(self, temp_db):
        """Test that init_db creates required indexes."""
        with get_db_connection(temp_db) as conn:
            indexes = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index'
            """).fetchall()
            
            index_names = [idx['name'] for idx in indexes]
            assert 'idx_episodes_created' in index_names
            assert 'idx_episodes_model' in index_names
            assert 'idx_tasks_episode' in index_names


# ============================================================================
# EPISODE SAVING TESTS
# ============================================================================

class TestSaveEpisode:
    """Tests for saving episodes."""

    def test_save_episode_basic(self, temp_db):
        """Test basic episode saving."""
        save_episode(
            episode_id="test-123",
            model_name="test-model",
            total_reward=2.5,
            average_score=0.833,
            steps=3,
            completed=True,
            duration_seconds=10.5,
            db_path=temp_db
        )
        
        episode = get_episode("test-123", temp_db)
        
        assert episode is not None
        assert episode["episode"]["episode_id"] == "test-123"
        assert episode["episode"]["model_name"] == "test-model"
        assert episode["episode"]["total_reward"] == 2.5
        assert episode["episode"]["average_score"] == 0.833
        assert episode["episode"]["steps"] == 3
        assert episode["episode"]["completed"] == 1  # SQLite stores bool as int

    def test_save_episode_with_tasks(self, temp_db):
        """Test saving episode with tasks."""
        tasks = [
            {"task_id": 1, "reward": 1.0, "feedback": "Correct", "action": {"label": "spam"}},
            {"task_id": 2, "reward": 0.6, "feedback": "Good", "action": {"ranking": [1, 2, 0]}},
            {"task_id": 3, "reward": 0.9, "feedback": "Excellent", "action": {"action_type": "reply"}},
        ]
        
        save_episode(
            episode_id="test-456",
            model_name="test-model",
            total_reward=2.5,
            average_score=0.833,
            steps=3,
            completed=True,
            duration_seconds=10.5,
            tasks=tasks,
            db_path=temp_db
        )
        
        episode = get_episode("test-456", temp_db)
        
        assert len(episode["tasks"]) == 3
        assert episode["tasks"][0]["task_id"] == 1
        assert episode["tasks"][0]["reward"] == 1.0
        assert episode["tasks"][1]["task_id"] == 2
        assert episode["tasks"][2]["task_id"] == 3

    def test_save_episode_updates_existing(self, temp_db):
        """Test that saving existing episode updates it."""
        # Save initial episode
        save_episode(
            episode_id="test-update",
            model_name="test-model",
            total_reward=1.0,
            average_score=0.5,
            steps=2,
            completed=False,
            duration_seconds=5.0,
            db_path=temp_db
        )
        
        # Update episode
        save_episode(
            episode_id="test-update",
            model_name="test-model",
            total_reward=2.5,
            average_score=0.833,
            steps=3,
            completed=True,
            duration_seconds=10.5,
            db_path=temp_db
        )
        
        episode = get_episode("test-update", temp_db)
        
        assert episode["episode"]["total_reward"] == 2.5
        assert episode["episode"]["average_score"] == 0.833
        assert episode["episode"]["completed"] == 1

    def test_save_episode_updates_model_performance(self, temp_db):
        """Test that saving episode updates model performance."""
        save_episode(
            episode_id="test-perf-1",
            model_name="perf-test-model",
            average_score=0.8,
            db_path=temp_db
        )
        
        save_episode(
            episode_id="test-perf-2",
            model_name="perf-test-model",
            average_score=0.9,
            db_path=temp_db
        )
        
        stats = get_model_stats("perf-test-model", temp_db)
        
        assert stats is not None
        assert stats["episode_count"] >= 2


# ============================================================================
# EPISODE RETRIEVAL TESTS
# ============================================================================

class TestGetEpisode:
    """Tests for retrieving episodes."""

    def test_get_episode_exists(self, populated_db):
        """Test retrieving existing episode."""
        episode = get_episode("test-episode-1", populated_db)
        
        assert episode is not None
        assert "episode" in episode
        assert "tasks" in episode

    def test_get_episode_not_found(self, populated_db):
        """Test retrieving non-existing episode."""
        episode = get_episode("non-existent", populated_db)
        
        assert episode is None

    def test_get_recent_episodes(self, populated_db):
        """Test retrieving recent episodes."""
        episodes = get_recent_episodes(limit=2, db_path=populated_db)
        
        assert len(episodes) <= 2
        assert all("episode_id" in ep for ep in episodes)


# ============================================================================
# MODEL STATISTICS TESTS
# ============================================================================

class TestModelStats:
    """Tests for model statistics."""

    def test_get_model_stats_exists(self, populated_db):
        """Test retrieving stats for existing model."""
        stats = get_model_stats("test-model-v1", populated_db)
        
        assert stats is not None
        assert stats["model_name"] == "test-model-v1"
        assert stats["episode_count"] >= 2

    def test_get_model_stats_not_found(self, populated_db):
        """Test retrieving stats for non-existing model."""
        stats = get_model_stats("non-existent-model", populated_db)
        
        assert stats is None

    def test_get_model_stats_task_averages(self, populated_db):
        """Test that model stats include task averages."""
        stats = get_model_stats("test-model-v1", populated_db)
        
        assert "task_1_avg" in stats
        assert "task_2_avg" in stats
        assert "task_3_avg" in stats


# ============================================================================
# ANALYTICS TESTS
# ============================================================================

class TestAnalytics:
    """Tests for analytics queries."""

    def test_get_analytics_structure(self, populated_db):
        """Test analytics returns expected structure."""
        analytics = get_analytics(populated_db)
        
        assert "overall" in analytics
        assert "task_difficulty" in analytics
        assert "trend" in analytics
        assert "leaderboard" in analytics

    def test_get_analytics_overall(self, populated_db):
        """Test overall analytics."""
        analytics = get_analytics(populated_db)
        overall = analytics["overall"]
        
        assert overall["total_episodes"] == 3
        assert overall["num_models"] == 2
        assert overall["overall_avg_score"] is not None
        assert overall["overall_completion_rate"] is not None

    def test_get_analytics_task_difficulty(self, populated_db):
        """Test task difficulty analytics."""
        analytics = get_analytics(populated_db)
        task_diff = analytics["task_difficulty"]
        
        assert len(task_diff) == 3  # 3 tasks
        for task in task_diff:
            assert "task_id" in task
            assert "avg_reward" in task
            assert "num_attempts" in task

    def test_get_analytics_leaderboard(self, populated_db):
        """Test leaderboard analytics."""
        analytics = get_analytics(populated_db)
        leaderboard = analytics["leaderboard"]
        
        assert len(leaderboard) <= 2  # 2 models
        # Should be ordered by avg_score descending
        if len(leaderboard) > 1:
            assert leaderboard[0]["avg_score"] >= leaderboard[1]["avg_score"]


# ============================================================================
# DATABASE CLEANUP TESTS
# ============================================================================

class TestDatabaseCleanup:
    """Tests for database cleanup operations."""

    def test_clear_database(self, populated_db):
        """Test clearing database."""
        # Verify data exists
        episodes = get_recent_episodes(limit=10, db_path=populated_db)
        assert len(episodes) > 0
        
        # Clear database
        clear_database(populated_db)
        
        # Verify data is cleared
        episodes = get_recent_episodes(limit=10, db_path=populated_db)
        assert len(episodes) == 0

    def test_clear_database_preserves_tables(self, populated_db):
        """Test that clear_database preserves table structure."""
        clear_database(populated_db)
        
        # Should still be able to save after clearing
        save_episode(
            episode_id="test-after-clear",
            model_name="test-model",
            db_path=populated_db
        )
        
        episode = get_episode("test-after-clear", populated_db)
        assert episode is not None


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestDatabaseEdgeCases:
    """Tests for database edge cases."""

    def test_save_episode_null_values(self, temp_db):
        """Test saving episode with null values."""
        save_episode(
            episode_id="test-nulls",
            db_path=temp_db
        )
        
        episode = get_episode("test-nulls", temp_db)
        
        assert episode is not None
        assert episode["episode"]["model_name"] == "unknown"
        assert episode["episode"]["total_reward"] == 0.0

    def test_get_recent_episodes_zero_limit(self, populated_db):
        """Test getting recent episodes with limit 0."""
        episodes = get_recent_episodes(limit=0, db_path=populated_db)
        
        assert len(episodes) == 0

    def test_get_recent_episodes_large_limit(self, populated_db):
        """Test getting recent episodes with large limit."""
        episodes = get_recent_episodes(limit=1000, db_path=populated_db)
        
        assert len(episodes) == 3  # Only 3 episodes exist


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
