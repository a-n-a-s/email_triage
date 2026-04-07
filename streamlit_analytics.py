"""
Streamlit Analytics Dashboard for Email Triage Environment.

Provides real-time visualization of:
- Episode history and performance trends
- Model leaderboard and comparisons
- Task-level analytics and difficulty analysis
- Confusion matrices for classification tasks
- Response time distributions

Usage:
    streamlit run streamlit_analytics.py

    # Or with custom database path:
    EMAIL_TRIAGE_DB=/path/to/db.sqlite streamlit run streamlit_analytics.py
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ============================================================================
# CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Email Triage Analytics",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATABASE_PATH = st.getenv("EMAIL_TRIAGE_DB", "email_triage.db")


# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

@st.cache_data(ttl=10)  # Cache for 10 seconds
def get_analytics_data(db_path: str = DATABASE_PATH) -> Dict[str, Any]:
    """Fetch analytics data from database."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Overall stats
        overall = pd.read_sql_query("""
            SELECT
                COUNT(*) as total_episodes,
                AVG(average_score) as overall_avg_score,
                CAST(SUM(CASE WHEN completed THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as overall_completion_rate,
                COUNT(DISTINCT model_name) as num_models,
                MIN(created_at) as first_episode,
                MAX(created_at) as last_episode
            FROM episodes
        """, conn)

        # Task difficulty analysis
        task_difficulty = pd.read_sql_query("""
            SELECT task_id, AVG(reward) as avg_reward, COUNT(*) as num_attempts,
                   MIN(reward) as min_reward, MAX(reward) as max_reward,
                   STDDEV(reward) as std_reward
            FROM tasks
            GROUP BY task_id
            ORDER BY task_id
        """, conn)

        # Performance trend (last 100 episodes)
        trend = pd.read_sql_query("""
            SELECT episode_id, model_name, average_score, total_reward,
                   steps, completed, created_at
            FROM episodes
            ORDER BY created_at DESC
            LIMIT 100
        """, conn)

        # Model leaderboard
        leaderboard = pd.read_sql_query("""
            SELECT
                mp.model_name,
                mp.episode_count,
                mp.avg_score,
                CAST(SUM(CASE WHEN e.completed THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as completion_rate,
                AVG(e.steps) as avg_steps,
                AVG(e.duration_seconds) as avg_duration
            FROM model_performance mp
            LEFT JOIN episodes e ON mp.model_name = e.model_name
            GROUP BY mp.model_name, mp.episode_count, mp.avg_score
            ORDER BY mp.avg_score DESC
            LIMIT 20
        """, conn)

        # Per-task performance by model
        task_by_model = pd.read_sql_query("""
            SELECT
                e.model_name,
                t.task_id,
                AVG(t.reward) as avg_reward,
                COUNT(*) as attempts
            FROM tasks t
            JOIN episodes e ON t.episode_id = e.episode_id
            GROUP BY e.model_name, t.task_id
            ORDER BY e.model_name, t.task_id
        """, conn)

        # Recent episodes
        recent = pd.read_sql_query("""
            SELECT episode_id, model_name, average_score, total_reward,
                   steps, completed, duration_seconds, created_at
            FROM episodes
            ORDER BY created_at DESC
            LIMIT 20
        """, conn)

        # Hourly activity
        hourly_activity = pd.read_sql_query("""
            SELECT
                strftime('%H', created_at) as hour,
                COUNT(*) as episode_count,
                AVG(average_score) as avg_score
            FROM episodes
            GROUP BY hour
            ORDER BY hour
        """, conn)

        # Daily activity (last 30 days)
        daily_activity = pd.read_sql_query("""
            SELECT
                DATE(created_at) as date,
                COUNT(*) as episode_count,
                AVG(average_score) as avg_score
            FROM episodes
            WHERE created_at >= DATE('now', '-30 days')
            GROUP BY date
            ORDER BY date
        """, conn)

        conn.close()

        return {
            "overall": overall,
            "task_difficulty": task_difficulty,
            "trend": trend,
            "leaderboard": leaderboard,
            "task_by_model": task_by_model,
            "recent": recent,
            "hourly_activity": hourly_activity,
            "daily_activity": daily_activity,
        }

    except Exception as e:
        st.error(f"Error loading analytics data: {e}")
        return {}


# ============================================================================
# VISUALIZATION COMPONENTS
# ============================================================================

def render_kpi_cards(overall: pd.DataFrame) -> None:
    """Render KPI summary cards."""
    if overall.empty:
        st.warning("No data available")
        return

    row = overall.iloc[0]
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📧 Total Episodes",
            value=f"{row['total_episodes']:,}",
            help="Total number of episodes run"
        )
    
    with col2:
        avg_score = row['overall_avg_score'] or 0
        st.metric(
            label="📊 Average Score",
            value=f"{avg_score:.3f}",
            help="Average score across all episodes (0.0 - 1.0)"
        )
    
    with col3:
        completion_rate = row['overall_completion_rate'] or 0
        st.metric(
            label="✅ Completion Rate",
            value=f"{completion_rate:.1%}",
            help="Percentage of episodes completed successfully"
        )
    
    with col4:
        st.metric(
            label="🤖 Models Tested",
            value=row['num_models'],
            help="Number of unique models evaluated"
        )


def render_performance_trend(trend: pd.DataFrame) -> None:
    """Render performance trend over time."""
    if trend.empty:
        st.warning("No trend data available")
        return

    st.subheader("📈 Performance Trend (Last 100 Episodes)")
    
    # Convert created_at to datetime
    trend['created_at'] = pd.to_datetime(trend['created_at'])
    
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add score line
    fig.add_trace(
        go.Scatter(
            x=trend['created_at'],
            y=trend['average_score'],
            name="Average Score",
            line=dict(color="#1f77b4", width=2),
            mode='lines+markers',
            marker=dict(size=4)
        ),
        secondary_y=False
    )
    
    # Add steps line
    fig.add_trace(
        go.Scatter(
            x=trend['created_at'],
            y=trend['steps'],
            name="Steps",
            line=dict(color="#ff7f0e", width=2, dash='dash'),
            mode='lines'
        ),
        secondary_y=True
    )
    
    # Update layout
    fig.update_layout(
        height=400,
        hovermode='x unified',
        showlegend=True,
        legend=dict(orientation="h", y=1.1, x=0)
    )
    
    fig.update_xaxes(title_text="Time")
    fig.update_yaxes(title_text="Score (0-1)", secondary_y=False, range=[0, 1.1])
    fig.update_yaxes(title_text="Steps", secondary_y=True)
    
    st.plotly_chart(fig, use_container_width=True)


def render_task_difficulty(task_difficulty: pd.DataFrame) -> None:
    """Render task difficulty analysis."""
    if task_difficulty.empty:
        st.warning("No task difficulty data available")
        return

    st.subheader("📊 Task Difficulty Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Bar chart of average rewards by task
        fig = px.bar(
            task_difficulty,
            x='task_id',
            y='avg_reward',
            error_y='std_reward',
            title="Average Reward by Task",
            labels={'task_id': 'Task ID', 'avg_reward': 'Average Reward'},
            color='avg_reward',
            color_continuous_scale='RdYlGn'
        )
        fig.update_traces(marker_line_width=0)
        fig.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Task statistics table
        stats_df = task_difficulty.copy()
        stats_df['task_name'] = stats_df['task_id'].map({
            1: 'Spam Classification',
            2: 'Urgency Ranking',
            3: 'Action & Reply'
        })
        
        stats_display = stats_df[['task_name', 'avg_reward', 'num_attempts', 'min_reward', 'max_reward']].copy()
        stats_display.columns = ['Task', 'Avg Reward', 'Attempts', 'Min', 'Max']
        stats_display['Avg Reward'] = stats_display['Avg Reward'].apply(lambda x: f"{x:.3f}")
        stats_display['Min'] = stats_display['Min'].apply(lambda x: f"{x:.3f}")
        stats_display['Max'] = stats_display['Max'].apply(lambda x: f"{x:.3f}")
        
        st.dataframe(stats_display, hide_index=True, use_container_width=True)


def render_model_leaderboard(leaderboard: pd.DataFrame) -> None:
    """Render model performance leaderboard."""
    if leaderboard.empty:
        st.warning("No model performance data available")
        return

    st.subheader("🏆 Model Leaderboard")
    
    # Format for display
    display_df = leaderboard.copy()
    display_df['avg_score'] = display_df['avg_score'].apply(lambda x: f"{x:.3f}")
    display_df['completion_rate'] = display_df['completion_rate'].apply(lambda x: f"{x:.1%}")
    display_df['avg_steps'] = display_df['avg_steps'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")
    display_df['avg_duration'] = display_df['avg_duration'].apply(lambda x: f"{x:.1f}s" if pd.notna(x) else "N/A")
    
    display_df = display_df.rename(columns={
        'model_name': 'Model',
        'episode_count': 'Episodes',
        'avg_score': 'Avg Score',
        'completion_rate': 'Completion',
        'avg_steps': 'Avg Steps',
        'avg_duration': 'Avg Duration'
    })
    
    # Color code the scores
    def score_color(val):
        try:
            score = float(val)
            if score >= 0.9:
                return "background-color: #28a745; color: white"
            elif score >= 0.7:
                return "background-color: #ffc107; color: black"
            else:
                return "background-color: #dc3545; color: white"
        except:
            return ""
    
    styled = display_df.style.applymap(score_color, subset=['Avg Score'])
    st.dataframe(styled, hide_index=True, use_container_width=True)
    
    # Model comparison chart
    if len(leaderboard) > 1:
        fig = px.bar(
            leaderboard.head(10),
            x='model_name',
            y='avg_score',
            title="Top 10 Models by Average Score",
            labels={'model_name': 'Model', 'avg_score': 'Average Score'},
            color='avg_score',
            color_continuous_scale='Viridis'
        )
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)


def render_task_performance_by_model(task_by_model: pd.DataFrame) -> None:
    """Render task performance breakdown by model."""
    if task_by_model.empty:
        st.warning("No task-by-model data available")
        return

    st.subheader("📊 Task Performance by Model")
    
    # Pivot for heatmap
    pivot = task_by_model.pivot(index='model_name', columns='task_id', values='avg_reward')
    
    fig = px.imshow(
        pivot,
        labels=dict(x="Task", y="Model", color="Avg Reward"),
        x=['Spam Class.', 'Ranking', 'Action & Reply'],
        color_continuous_scale='RdYlGn',
        aspect='auto'
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)


def render_activity_analysis(hourly: pd.DataFrame, daily: pd.DataFrame) -> None:
    """Render activity pattern analysis."""
    st.subheader("🕐 Activity Patterns")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not hourly.empty:
            fig = px.bar(
                hourly,
                x='hour',
                y='episode_count',
                title="Episodes by Hour of Day",
                labels={'hour': 'Hour', 'episode_count': 'Episodes'},
                color='episode_count',
                color_continuous_scale='Blues'
            )
            fig.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        if not daily.empty:
            daily['date'] = pd.to_datetime(daily['date'])
            fig = px.line(
                daily,
                x='date',
                y='episode_count',
                title="Daily Episode Count (Last 30 Days)",
                labels={'date': 'Date', 'episode_count': 'Episodes'},
                markers=True
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)


def render_recent_episodes(recent: pd.DataFrame) -> None:
    """Render recent episodes table."""
    if recent.empty:
        st.warning("No recent episode data available")
        return

    st.subheader("📋 Recent Episodes")
    
    # Format for display
    display_df = recent.copy()
    display_df['created_at'] = pd.to_datetime(display_df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
    display_df['average_score'] = display_df['average_score'].apply(lambda x: f"{x:.3f}")
    display_df['total_reward'] = display_df['total_reward'].apply(lambda x: f"{x:.2f}")
    display_df['duration_seconds'] = display_df['duration_seconds'].apply(lambda x: f"{x:.1f}s" if pd.notna(x) else "N/A")
    display_df['completed'] = display_df['completed'].apply(lambda x: "✅" if x else "❌")
    
    display_df = display_df.rename(columns={
        'episode_id': 'Episode ID',
        'model_name': 'Model',
        'average_score': 'Score',
        'total_reward': 'Total Reward',
        'steps': 'Steps',
        'completed': 'Done',
        'duration_seconds': 'Duration',
        'created_at': 'Timestamp'
    })
    
    st.dataframe(display_df, hide_index=True, use_container_width=True)


def render_database_info() -> None:
    """Render database information and export options."""
    st.subheader("💾 Database Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Database Path:** `{DATABASE_PATH}`")
        st.write(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    with col2:
        # Export options
        st.write("**Export Data:**")
        
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            
            # Export episodes
            episodes_df = pd.read_sql_query("SELECT * FROM episodes ORDER BY created_at DESC", conn)
            csv_episodes = episodes_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Episodes (CSV)",
                data=csv_episodes,
                file_name=f"episodes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
            # Export tasks
            tasks_df = pd.read_sql_query("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 1000", conn)
            csv_tasks = tasks_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Tasks (CSV)",
                data=csv_tasks,
                file_name=f"tasks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
            conn.close()
        except Exception as e:
            st.error(f"Export failed: {e}")


# ============================================================================
# MAIN DASHBOARD
# ============================================================================

def main():
    """Main dashboard application."""
    
    # Header
    st.title("📧 Email Triage Analytics Dashboard")
    st.markdown("""
        Real-time analytics and performance tracking for the Email Triage Environment.
        Track model performance, task difficulty, and episode history.
    """)
    
    # Auto-refresh option
    auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh (10s)", value=False)
    
    # Load data
    with st.spinner("Loading analytics data..."):
        data = get_analytics_data()
    
    if not data:
        st.error("Failed to load analytics data. Make sure the database exists and the server is running.")
        return
    
    # Render KPI cards
    render_kpi_cards(data.get('overall', pd.DataFrame()))
    
    st.divider()
    
    # Main visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        render_performance_trend(data.get('trend', pd.DataFrame()))
    
    with col2:
        render_task_difficulty(data.get('task_difficulty', pd.DataFrame()))
    
    st.divider()
    
    # Model leaderboard and task performance
    col1, col2 = st.columns([2, 1])
    
    with col1:
        render_model_leaderboard(data.get('leaderboard', pd.DataFrame()))
    
    with col2:
        render_task_performance_by_model(data.get('task_by_model', pd.DataFrame()))
    
    st.divider()
    
    # Activity patterns
    render_activity_analysis(
        data.get('hourly_activity', pd.DataFrame()),
        data.get('daily_activity', pd.DataFrame())
    )
    
    st.divider()
    
    # Recent episodes
    render_recent_episodes(data.get('recent', pd.DataFrame()))
    
    st.divider()
    
    # Database info and exports
    render_database_info()
    
    # Footer
    st.markdown("---")
    st.caption(
        "Email Triage Analytics Dashboard | "
        f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Database: `{DATABASE_PATH}`"
    )
    
    # Auto-refresh
    if auto_refresh:
        import time
        time.sleep(10)
        st.rerun()


if __name__ == "__main__":
    main()
