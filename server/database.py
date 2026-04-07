"""
SQLite Database for Episode Persistence and Analytics.

Stores:
- Episode history (scores, rewards, completion status)
- Model performance tracking
- Task-level analytics
- Timestamps and metadata
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import os

DATABASE_PATH = os.getenv("EMAIL_TRIAGE_DB", "email_triage.db")


@contextmanager
def get_db_connection(db_path: str = DATABASE_PATH):
    """Context manager for database connections."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = DATABASE_PATH):
    """Initialize database with required tables."""
    with get_db_connection(db_path) as conn:
        conn.executescript("""
            -- Episodes table: stores complete episode records
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id TEXT UNIQUE NOT NULL,
                model_name TEXT,
                model_config TEXT,
                total_reward REAL,
                average_score REAL,
                steps INTEGER,
                completed BOOLEAN,
                duration_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Tasks table: stores individual task results
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id TEXT NOT NULL,
                task_id INTEGER NOT NULL,
                reward REAL,
                feedback TEXT,
                action TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (episode_id) REFERENCES episodes(episode_id)
            );
            
            -- Models table: tracks model performance over time
            CREATE TABLE IF NOT EXISTS model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                episode_count INTEGER DEFAULT 1,
                avg_score REAL,
                avg_task1_score REAL,
                avg_task2_score REAL,
                avg_task3_score REAL,
                completion_rate REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(model_name)
            );
            
            -- Indexes for faster queries
            CREATE INDEX IF NOT EXISTS idx_episodes_created ON episodes(created_at);
            CREATE INDEX IF NOT EXISTS idx_episodes_model ON episodes(model_name);
            CREATE INDEX IF NOT EXISTS idx_tasks_episode ON tasks(episode_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_task ON tasks(task_id);
        """)
        conn.commit()


def save_episode(
    episode_id: str,
    model_name: str = "unknown",
    model_config: Optional[Dict] = None,
    total_reward: float = 0.0,
    average_score: float = 0.0,
    steps: int = 0,
    completed: bool = False,
    duration_seconds: float = 0.0,
    tasks: Optional[List[Dict]] = None,
    db_path: str = DATABASE_PATH
):
    """Save episode results to database."""
    with get_db_connection(db_path) as conn:
        # Insert episode
        conn.execute("""
            INSERT INTO episodes (episode_id, model_name, model_config, total_reward, 
                                  average_score, steps, completed, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(episode_id) DO UPDATE SET
                total_reward = excluded.total_reward,
                average_score = excluded.average_score,
                steps = excluded.steps,
                completed = excluded.completed,
                duration_seconds = excluded.duration_seconds
        """, (
            episode_id, model_name, json.dumps(model_config or {}),
            total_reward, average_score, steps, completed, duration_seconds
        ))
        
        # Insert tasks
        if tasks:
            for task in tasks:
                conn.execute("""
                    INSERT INTO tasks (episode_id, task_id, reward, feedback, action)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    episode_id,
                    task.get("task_id", 0),
                    task.get("reward", 0.0),
                    task.get("feedback", ""),
                    json.dumps(task.get("action", {}))
                ))
        
        # Update model performance
        conn.execute("""
            INSERT INTO model_performance (model_name, episode_count, avg_score)
            VALUES (?, 1, ?)
            ON CONFLICT(model_name) DO UPDATE SET
                episode_count = model_performance.episode_count + 1,
                avg_score = (
                    SELECT AVG(average_score) FROM episodes WHERE model_name = ?
                ),
                last_updated = CURRENT_TIMESTAMP
        """, (model_name, average_score, model_name))
        
        conn.commit()


def get_episode(episode_id: str, db_path: str = DATABASE_PATH) -> Optional[Dict]:
    """Get episode by ID with its tasks."""
    with get_db_connection(db_path) as conn:
        episode = conn.execute(
            "SELECT * FROM episodes WHERE episode_id = ?", (episode_id,)
        ).fetchone()
        
        if not episode:
            return None
        
        tasks = conn.execute(
            "SELECT * FROM tasks WHERE episode_id = ?", (episode_id,)
        ).fetchall()
        
        return {
            "episode": dict(episode),
            "tasks": [dict(t) for t in tasks]
        }


def get_recent_episodes(limit: int = 10, db_path: str = DATABASE_PATH) -> List[Dict]:
    """Get most recent episodes."""
    with get_db_connection(db_path) as conn:
        episodes = conn.execute("""
            SELECT * FROM episodes 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(e) for e in episodes]


def get_model_stats(model_name: str, db_path: str = DATABASE_PATH) -> Optional[Dict]:
    """Get aggregated statistics for a model."""
    with get_db_connection(db_path) as conn:
        stats = conn.execute("""
            SELECT 
                model_name,
                episode_count,
                avg_score,
                completion_rate,
                last_updated
            FROM model_performance
            WHERE model_name = ?
        """, (model_name,)).fetchone()
        
        if not stats:
            return None
        
        # Get per-task averages
        task_avgs = conn.execute("""
            SELECT task_id, AVG(reward) as avg_reward
            FROM tasks t
            JOIN episodes e ON t.episode_id = e.episode_id
            WHERE e.model_name = ?
            GROUP BY task_id
        """, (model_name,)).fetchall()
        
        result = dict(stats)
        result["task_1_avg"] = next((t["avg_reward"] for t in task_avgs if t["task_id"] == 1), 0.0)
        result["task_2_avg"] = next((t["avg_reward"] for t in task_avgs if t["task_id"] == 2), 0.0)
        result["task_3_avg"] = next((t["avg_reward"] for t in task_avgs if t["task_id"] == 3), 0.0)
        
        return result


def get_analytics(db_path: str = DATABASE_PATH) -> Dict[str, Any]:
    """Get overall analytics dashboard data."""
    with get_db_connection(db_path) as conn:
        # Overall stats - calculate completion rate from completed column
        overall = conn.execute("""
            SELECT
                COUNT(*) as total_episodes,
                AVG(average_score) as overall_avg_score,
                CAST(SUM(CASE WHEN completed THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as overall_completion_rate,
                COUNT(DISTINCT model_name) as num_models
            FROM episodes
        """).fetchone()

        # Task difficulty analysis
        task_difficulty = conn.execute("""
            SELECT task_id, AVG(reward) as avg_reward, COUNT(*) as num_attempts
            FROM tasks
            GROUP BY task_id
            ORDER BY task_id
        """).fetchall()

        # Recent performance trend (last 20 episodes)
        trend = conn.execute("""
            SELECT episode_id, average_score, created_at
            FROM episodes
            ORDER BY created_at DESC
            LIMIT 20
        """).fetchall()

        # Model leaderboard - calculate completion rate from episodes
        leaderboard = conn.execute("""
            SELECT 
                mp.model_name, 
                mp.episode_count, 
                mp.avg_score,
                CAST(SUM(CASE WHEN e.completed THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as completion_rate
            FROM model_performance mp
            LEFT JOIN episodes e ON mp.model_name = e.model_name
            GROUP BY mp.model_name, mp.episode_count, mp.avg_score
            ORDER BY mp.avg_score DESC
            LIMIT 10
        """).fetchall()

        return {
            "overall": dict(overall) if overall else {},
            "task_difficulty": [dict(t) for t in task_difficulty],
            "trend": [dict(t) for t in trend],
            "leaderboard": [dict(m) for m in leaderboard]
        }


def clear_database(db_path: str = DATABASE_PATH):
    """Clear all data from database (for testing)."""
    with get_db_connection(db_path) as conn:
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM episodes")
        conn.execute("DELETE FROM model_performance")
        conn.commit()


# Initialize database on module import
try:
    init_db()
except Exception as e:
    print(f"Warning: Could not initialize database: {e}")
