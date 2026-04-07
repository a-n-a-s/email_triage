# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Email Triage Environment.

Defines the Action and Observation shapes that the agent uses
to interact with the environment.
"""

from typing import Optional
from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class EmailTriageAction(Action):
    """
    What the agent sends to the environment on each step.

    Fields:
    - task_id:    which task is being attempted (1, 2, or 3)
    - label:      for Task 1 — "spam" or "not_spam"
    - ranking:    for Task 2 — list like [2, 0, 1] (indices ordered by urgency)
    - action_type:for Task 3 — "reply", "forward", "archive", or "delete"
    - reply_text: for Task 3 — the reply message the agent writes
    """

    task_id: Optional[int] = Field(None, description="Task to attempt: 1 (easy), 2 (medium), 3 (hard)")
    label: Optional[str] = Field(None, description="Task 1: 'spam' or 'not_spam'")
    ranking: Optional[list[int]] = Field(None, description="Task 2: email indices ordered by urgency")
    action_type: Optional[str] = Field(None, description="Task 3: 'reply', 'forward', 'archive', 'delete'")
    reply_text: Optional[str] = Field(None, description="Task 3: reply message to write")


class EmailTriageObservation(Observation):
    """
    What the environment sends back to the agent after each step.

    Fields:
    - task_id:       which task this observation is for
    - task_description: plain English description of what to do
    - emails:        list of email dicts the agent must process
    - reward:        score received for the last action (0.0 to 1.0)
    - done:          True when the episode is complete
    - feedback:      human-readable explanation of the reward given
    """

    task_id: int = Field(default=1, description="Current task ID")
    task_description: str = Field(default="", description="What the agent needs to do")
    emails: list[dict] = Field(default_factory=list, description="Emails to process")
    reward: float = Field(default=0.0, description="Reward for the last action")
    done: bool = Field(default=False, description="True when episode is over")
    feedback: str = Field(default="", description="Explanation of the reward")
    
    
    
    