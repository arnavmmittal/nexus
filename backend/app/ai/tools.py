"""Tools that Jarvis can use to interact with user data and systems."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillXPLog
from app.models.goal import Goal, GoalProgressLog
from app.models.memory import Fact, Pattern


# Tool definitions for Claude
TOOLS = [
    # ============ SKILL TOOLS ============
    {
        "name": "create_skill",
        "description": "Create a new skill to track the user's abilities and progress. Use this when the user mentions learning something new or wants to track a skill.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the skill (e.g., 'Python', 'Public Speaking', 'Guitar')"
                },
                "category": {
                    "type": "string",
                    "description": "Category of the skill (e.g., 'programming', 'communication', 'music', 'fitness', 'finance')"
                }
            },
            "required": ["name", "category"]
        }
    },
    {
        "name": "list_skills",
        "description": "Get all skills the user is tracking, optionally filtered by category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter"
                }
            },
            "required": []
        }
    },
    {
        "name": "add_skill_xp",
        "description": "Add experience points (XP) to a skill. Use this when the user practices or demonstrates a skill. XP causes level ups.",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Name of the skill to add XP to"
                },
                "xp_amount": {
                    "type": "integer",
                    "description": "Amount of XP to add (typically 10-100 based on effort)"
                },
                "description": {
                    "type": "string",
                    "description": "What the user did to earn this XP"
                }
            },
            "required": ["skill_name", "xp_amount"]
        }
    },
    {
        "name": "delete_skill",
        "description": "Delete a skill the user no longer wants to track.",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Name of the skill to delete"
                }
            },
            "required": ["skill_name"]
        }
    },

    # ============ GOAL TOOLS ============
    {
        "name": "create_goal",
        "description": "Create a new goal for the user to work towards. Use this when the user expresses a desire to achieve something.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the goal (e.g., 'Run a marathon', 'Save $10,000')"
                },
                "domain": {
                    "type": "string",
                    "description": "Life domain (e.g., 'health', 'finance', 'career', 'relationships', 'learning')"
                },
                "target_value": {
                    "type": "number",
                    "description": "Target numeric value if applicable (e.g., 10000 for savings goal)"
                },
                "unit": {
                    "type": "string",
                    "description": "Unit of measurement (e.g., 'dollars', 'miles', 'hours')"
                },
                "deadline": {
                    "type": "string",
                    "description": "Deadline in YYYY-MM-DD format (optional)"
                }
            },
            "required": ["title", "domain"]
        }
    },
    {
        "name": "list_goals",
        "description": "Get all goals, optionally filtered by status or domain.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "completed", "paused", "cancelled"],
                    "description": "Filter by goal status"
                },
                "domain": {
                    "type": "string",
                    "description": "Filter by life domain"
                }
            },
            "required": []
        }
    },
    {
        "name": "update_goal_progress",
        "description": "Update progress on a goal. Use this when the user makes progress towards a goal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_title": {
                    "type": "string",
                    "description": "Title of the goal to update"
                },
                "new_value": {
                    "type": "number",
                    "description": "New progress value"
                }
            },
            "required": ["goal_title", "new_value"]
        }
    },
    {
        "name": "complete_goal",
        "description": "Mark a goal as completed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_title": {
                    "type": "string",
                    "description": "Title of the goal to complete"
                }
            },
            "required": ["goal_title"]
        }
    },
    {
        "name": "delete_goal",
        "description": "Delete a goal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_title": {
                    "type": "string",
                    "description": "Title of the goal to delete"
                }
            },
            "required": ["goal_title"]
        }
    },

    # ============ MEMORY/FACT TOOLS ============
    {
        "name": "remember_fact",
        "description": "Store a fact about the user for future reference. Use this to remember preferences, important info, or anything the user shares about themselves.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["preference", "identity", "goal", "value", "relationship", "work", "health", "other"],
                    "description": "Category of the fact"
                },
                "key": {
                    "type": "string",
                    "description": "Short key/label for the fact (e.g., 'favorite_color', 'job_title')"
                },
                "value": {
                    "type": "string",
                    "description": "The actual information to remember"
                }
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "recall_facts",
        "description": "Retrieve stored facts about the user, optionally filtered by category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter"
                }
            },
            "required": []
        }
    },
    {
        "name": "forget_fact",
        "description": "Delete a stored fact about the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key of the fact to delete"
                }
            },
            "required": ["key"]
        }
    },

    # ============ REMINDERS & TIMERS ============
    {
        "name": "set_reminder",
        "description": "Set a reminder for the user. Store it as a fact with timing info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "What to remind the user about"
                },
                "when": {
                    "type": "string",
                    "description": "When to remind (e.g., 'tomorrow at 9am', 'in 2 hours', '2024-03-20 14:00')"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Priority level"
                }
            },
            "required": ["message", "when"]
        }
    },
    {
        "name": "list_reminders",
        "description": "List all active reminders.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "start_timer",
        "description": "Start a timer or stopwatch for the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration in minutes (for countdown timer)"
                },
                "label": {
                    "type": "string",
                    "description": "Label for the timer (e.g., 'Pomodoro', 'Workout')"
                }
            },
            "required": ["label"]
        }
    },
    {
        "name": "start_pomodoro",
        "description": "Start a Pomodoro session (25 min work, 5 min break).",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "What task the user is working on"
                }
            },
            "required": ["task"]
        }
    },

    # ============ NOTES & JOURNAL ============
    {
        "name": "create_note",
        "description": "Create a quick note or capture an idea for the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the note"
                },
                "content": {
                    "type": "string",
                    "description": "Content of the note"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to categorize the note"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "search_notes",
        "description": "Search through saved notes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "tag": {
                    "type": "string",
                    "description": "Filter by tag"
                }
            },
            "required": []
        }
    },
    {
        "name": "add_journal_entry",
        "description": "Add a journal entry for today. Use for reflections, daily logs, or gratitude.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The journal entry content"
                },
                "mood": {
                    "type": "string",
                    "enum": ["great", "good", "okay", "bad", "terrible"],
                    "description": "How the user is feeling"
                },
                "gratitude": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Things the user is grateful for"
                }
            },
            "required": ["content"]
        }
    },

    # ============ HABIT TRACKING ============
    {
        "name": "create_habit",
        "description": "Create a new habit to track daily.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the habit (e.g., 'Meditate', 'Read', 'Exercise')"
                },
                "frequency": {
                    "type": "string",
                    "enum": ["daily", "weekdays", "weekends", "weekly"],
                    "description": "How often to do this habit"
                },
                "target": {
                    "type": "string",
                    "description": "Target to hit (e.g., '20 minutes', '30 pages', '1 hour')"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "log_habit",
        "description": "Log that a habit was completed today.",
        "input_schema": {
            "type": "object",
            "properties": {
                "habit_name": {
                    "type": "string",
                    "description": "Name of the habit"
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes about the session"
                }
            },
            "required": ["habit_name"]
        }
    },
    {
        "name": "get_habit_streaks",
        "description": "Get current streaks for all habits.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },

    # ============ HEALTH & WELLNESS ============
    {
        "name": "log_water",
        "description": "Log water intake.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount_oz": {
                    "type": "number",
                    "description": "Amount in ounces"
                }
            },
            "required": ["amount_oz"]
        }
    },
    {
        "name": "log_sleep",
        "description": "Log sleep data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "number",
                    "description": "Hours slept"
                },
                "quality": {
                    "type": "string",
                    "enum": ["great", "good", "okay", "poor", "terrible"],
                    "description": "Sleep quality"
                }
            },
            "required": ["hours"]
        }
    },
    {
        "name": "log_workout",
        "description": "Log a workout or exercise session.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Type of workout (e.g., 'running', 'weights', 'yoga', 'cycling')"
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration in minutes"
                },
                "intensity": {
                    "type": "string",
                    "enum": ["light", "moderate", "intense"],
                    "description": "Workout intensity"
                },
                "notes": {
                    "type": "string",
                    "description": "Workout details"
                }
            },
            "required": ["type", "duration_minutes"]
        }
    },
    {
        "name": "log_mood",
        "description": "Log the user's current mood.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mood": {
                    "type": "string",
                    "enum": ["ecstatic", "happy", "content", "neutral", "sad", "anxious", "stressed", "angry"],
                    "description": "Current mood"
                },
                "notes": {
                    "type": "string",
                    "description": "What's contributing to this mood"
                },
                "energy_level": {
                    "type": "integer",
                    "description": "Energy level 1-10"
                }
            },
            "required": ["mood"]
        }
    },
    {
        "name": "get_health_summary",
        "description": "Get a summary of recent health metrics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default 7)"
                }
            },
            "required": []
        }
    },

    # ============ FINANCE TOOLS ============
    {
        "name": "log_expense",
        "description": "Log an expense or purchase.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "Amount spent"
                },
                "category": {
                    "type": "string",
                    "description": "Category (e.g., 'food', 'transport', 'entertainment', 'shopping')"
                },
                "description": {
                    "type": "string",
                    "description": "What was purchased"
                },
                "recurring": {
                    "type": "boolean",
                    "description": "Is this a recurring expense?"
                }
            },
            "required": ["amount", "category"]
        }
    },
    {
        "name": "log_income",
        "description": "Log income received.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "Amount received"
                },
                "source": {
                    "type": "string",
                    "description": "Source of income (e.g., 'salary', 'freelance', 'investment')"
                },
                "description": {
                    "type": "string",
                    "description": "Description"
                }
            },
            "required": ["amount", "source"]
        }
    },
    {
        "name": "get_spending_summary",
        "description": "Get a summary of spending by category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["week", "month", "year"],
                    "description": "Time period"
                }
            },
            "required": []
        }
    },
    {
        "name": "set_budget",
        "description": "Set a budget for a category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Budget category"
                },
                "amount": {
                    "type": "number",
                    "description": "Monthly budget amount"
                }
            },
            "required": ["category", "amount"]
        }
    },

    # ============ TASK & PROJECT MANAGEMENT ============
    {
        "name": "create_task",
        "description": "Create a task or to-do item.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Task title"
                },
                "project": {
                    "type": "string",
                    "description": "Project this task belongs to"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Task priority"
                },
                "due_date": {
                    "type": "string",
                    "description": "Due date (YYYY-MM-DD)"
                },
                "estimated_minutes": {
                    "type": "integer",
                    "description": "Estimated time to complete"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "list_tasks",
        "description": "List tasks, optionally filtered.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Filter by project"
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed"],
                    "description": "Filter by status"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Filter by priority"
                }
            },
            "required": []
        }
    },
    {
        "name": "complete_task",
        "description": "Mark a task as complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_title": {
                    "type": "string",
                    "description": "Title of the task"
                }
            },
            "required": ["task_title"]
        }
    },
    {
        "name": "create_project",
        "description": "Create a new project to organize tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Project name"
                },
                "description": {
                    "type": "string",
                    "description": "Project description"
                },
                "deadline": {
                    "type": "string",
                    "description": "Project deadline (YYYY-MM-DD)"
                }
            },
            "required": ["name"]
        }
    },

    # ============ CONTACTS & RELATIONSHIPS ============
    {
        "name": "add_contact",
        "description": "Add a contact or person to remember.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Person's name"
                },
                "relationship": {
                    "type": "string",
                    "description": "Relationship (e.g., 'friend', 'colleague', 'family')"
                },
                "notes": {
                    "type": "string",
                    "description": "Notes about this person"
                },
                "birthday": {
                    "type": "string",
                    "description": "Birthday (MM-DD)"
                },
                "contact_info": {
                    "type": "string",
                    "description": "Email, phone, or other contact info"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "find_contact",
        "description": "Look up information about a contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name to search for"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "log_interaction",
        "description": "Log an interaction with a contact (to maintain relationships).",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_name": {
                    "type": "string",
                    "description": "Name of the contact"
                },
                "type": {
                    "type": "string",
                    "enum": ["call", "meeting", "message", "email", "other"],
                    "description": "Type of interaction"
                },
                "notes": {
                    "type": "string",
                    "description": "Notes about the interaction"
                }
            },
            "required": ["contact_name", "type"]
        }
    },

    # ============ CALENDAR & SCHEDULING ============
    {
        "name": "add_event",
        "description": "Add an event to the calendar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Event title"
                },
                "datetime": {
                    "type": "string",
                    "description": "Date and time (YYYY-MM-DD HH:MM)"
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Event duration in minutes"
                },
                "location": {
                    "type": "string",
                    "description": "Event location"
                },
                "description": {
                    "type": "string",
                    "description": "Event description"
                }
            },
            "required": ["title", "datetime"]
        }
    },
    {
        "name": "get_schedule",
        "description": "Get the schedule for a day or date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date to check (YYYY-MM-DD), defaults to today"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look ahead"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_daily_briefing",
        "description": "Get a comprehensive daily briefing including schedule, tasks, goals, and reminders.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },

    # ============ UTILITY TOOLS ============
    {
        "name": "get_current_datetime",
        "description": "Get the current date and time.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "search_memory",
        "description": "Search through all stored memories, notes, and conversations semantically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "calculate",
        "description": "Perform mathematical calculations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression to evaluate (e.g., '15% of 200', '50 * 1.08', 'sqrt(144)')"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "convert_units",
        "description": "Convert between units of measurement.",
        "input_schema": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                    "description": "Value to convert"
                },
                "from_unit": {
                    "type": "string",
                    "description": "Unit to convert from"
                },
                "to_unit": {
                    "type": "string",
                    "description": "Unit to convert to"
                }
            },
            "required": ["value", "from_unit", "to_unit"]
        }
    },
    {
        "name": "get_weather",
        "description": "Get weather information (simulated for now).",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Location to get weather for"
                }
            },
            "required": []
        }
    },
    {
        "name": "web_search",
        "description": "Search the web for information (simulated - returns that real search would be needed).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "generate_random",
        "description": "Generate random numbers, pick from a list, or make decisions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["number", "choice", "coin", "dice"],
                    "description": "Type of random generation"
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Options to choose from (for 'choice' type)"
                },
                "min": {
                    "type": "integer",
                    "description": "Minimum value (for 'number' type)"
                },
                "max": {
                    "type": "integer",
                    "description": "Maximum value (for 'number' type)"
                }
            },
            "required": ["type"]
        }
    },
    {
        "name": "set_focus_mode",
        "description": "Enable or configure focus mode to minimize distractions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "description": "Enable or disable focus mode"
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "How long to stay in focus mode"
                },
                "allow_urgent": {
                    "type": "boolean",
                    "description": "Allow urgent notifications"
                }
            },
            "required": ["enabled"]
        }
    },
]


class ToolExecutor:
    """Executes tools on behalf of the AI."""

    def __init__(self, db: AsyncSession, user_id: UUID, vector_store=None):
        self.db = db
        self.user_id = user_id
        self.vector_store = vector_store

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool and return the result as a string."""
        try:
            # Check if this is an integration tool (jobs, email, browser, slack, github)
            try:
                from app.integrations.executor import is_integration_tool, execute_integration_tool
                if is_integration_tool(tool_name):
                    return await execute_integration_tool(tool_name, tool_input)
            except ImportError:
                pass  # Integrations not available

            # Otherwise, use built-in tools
            method = getattr(self, f"_tool_{tool_name}", None)
            if method is None:
                return f"Error: Unknown tool '{tool_name}'"
            result = await method(**tool_input)
            return json.dumps(result, default=str)
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    # ============ SKILL TOOLS ============

    async def _tool_create_skill(self, name: str, category: str) -> Dict[str, Any]:
        """Create a new skill."""
        result = await self.db.execute(
            select(Skill).where(
                Skill.user_id == self.user_id,
                Skill.name.ilike(name)
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return {"success": False, "error": f"Skill '{name}' already exists at level {existing.current_level}"}

        skill = Skill(
            user_id=self.user_id,
            name=name,
            category=category.lower(),
        )
        self.db.add(skill)
        await self.db.flush()

        return {
            "success": True,
            "message": f"Created skill '{name}' in category '{category}'",
            "skill": {
                "id": str(skill.id),
                "name": skill.name,
                "category": skill.category,
                "level": skill.current_level,
                "xp": skill.current_xp
            }
        }

    async def _tool_list_skills(self, category: Optional[str] = None) -> Dict[str, Any]:
        """List all skills."""
        query = select(Skill).where(Skill.user_id == self.user_id)
        if category:
            query = query.where(Skill.category.ilike(category))
        query = query.order_by(Skill.current_level.desc())

        result = await self.db.execute(query)
        skills = result.scalars().all()

        return {
            "success": True,
            "count": len(skills),
            "skills": [
                {
                    "name": s.name,
                    "category": s.category,
                    "level": s.current_level,
                    "xp": s.current_xp,
                    "total_xp": s.total_xp,
                    "xp_to_next_level": s.xp_for_next_level - s.current_xp,
                    "last_practiced": s.last_practiced.isoformat() if s.last_practiced else None
                }
                for s in skills
            ]
        }

    async def _tool_add_skill_xp(
        self,
        skill_name: str,
        xp_amount: int,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add XP to a skill."""
        result = await self.db.execute(
            select(Skill).where(
                Skill.user_id == self.user_id,
                Skill.name.ilike(skill_name)
            )
        )
        skill = result.scalar_one_or_none()

        if not skill:
            return {"success": False, "error": f"Skill '{skill_name}' not found. Create it first."}

        old_level = skill.current_level

        xp_log = SkillXPLog(
            skill_id=skill.id,
            xp_amount=xp_amount,
            source="jarvis",
            description=description,
        )
        self.db.add(xp_log)

        skill.current_xp += xp_amount
        skill.total_xp += xp_amount
        skill.last_practiced = datetime.utcnow()

        leveled_up = False
        while skill.current_xp >= skill.xp_for_next_level:
            skill.current_xp -= skill.xp_for_next_level
            skill.current_level += 1
            leveled_up = True

        await self.db.flush()

        response = {
            "success": True,
            "message": f"Added {xp_amount} XP to '{skill.name}'",
            "skill": {
                "name": skill.name,
                "level": skill.current_level,
                "xp": skill.current_xp,
                "xp_to_next_level": skill.xp_for_next_level - skill.current_xp
            }
        }

        if leveled_up:
            response["level_up"] = f"🎉 Level up! {skill.name} is now level {skill.current_level}!"

        return response

    async def _tool_delete_skill(self, skill_name: str) -> Dict[str, Any]:
        """Delete a skill."""
        result = await self.db.execute(
            select(Skill).where(
                Skill.user_id == self.user_id,
                Skill.name.ilike(skill_name)
            )
        )
        skill = result.scalar_one_or_none()

        if not skill:
            return {"success": False, "error": f"Skill '{skill_name}' not found"}

        await self.db.delete(skill)
        await self.db.flush()

        return {"success": True, "message": f"Deleted skill '{skill_name}'"}

    # ============ GOAL TOOLS ============

    async def _tool_create_goal(
        self,
        title: str,
        domain: str,
        target_value: Optional[float] = None,
        unit: Optional[str] = None,
        deadline: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new goal."""
        result = await self.db.execute(
            select(Goal).where(
                Goal.user_id == self.user_id,
                Goal.title.ilike(title)
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return {"success": False, "error": f"Goal '{title}' already exists"}

        goal = Goal(
            user_id=self.user_id,
            title=title,
            domain=domain.lower(),
            target_type="numeric" if target_value else "boolean",
            target_value=target_value,
            unit=unit,
            deadline=datetime.strptime(deadline, "%Y-%m-%d").date() if deadline else None,
        )
        self.db.add(goal)
        await self.db.flush()

        return {
            "success": True,
            "message": f"Created goal '{title}'",
            "goal": {
                "id": str(goal.id),
                "title": goal.title,
                "domain": goal.domain,
                "target_value": goal.target_value,
                "unit": goal.unit,
                "deadline": goal.deadline.isoformat() if goal.deadline else None
            }
        }

    async def _tool_list_goals(
        self,
        status: Optional[str] = None,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all goals."""
        query = select(Goal).where(Goal.user_id == self.user_id)
        if status:
            query = query.where(Goal.status == status)
        if domain:
            query = query.where(Goal.domain.ilike(domain))
        query = query.order_by(Goal.deadline.asc().nullslast())

        result = await self.db.execute(query)
        goals = result.scalars().all()

        return {
            "success": True,
            "count": len(goals),
            "goals": [
                {
                    "title": g.title,
                    "domain": g.domain,
                    "status": g.status,
                    "progress": f"{g.progress_percentage:.0f}%",
                    "current_value": g.current_value,
                    "target_value": g.target_value,
                    "unit": g.unit,
                    "deadline": g.deadline.isoformat() if g.deadline else None
                }
                for g in goals
            ]
        }

    async def _tool_update_goal_progress(
        self,
        goal_title: str,
        new_value: float
    ) -> Dict[str, Any]:
        """Update goal progress."""
        result = await self.db.execute(
            select(Goal).where(
                Goal.user_id == self.user_id,
                Goal.title.ilike(goal_title)
            )
        )
        goal = result.scalar_one_or_none()

        if not goal:
            return {"success": False, "error": f"Goal '{goal_title}' not found"}

        progress_log = GoalProgressLog(
            goal_id=goal.id,
            previous_value=goal.current_value,
            new_value=new_value,
        )
        self.db.add(progress_log)

        goal.current_value = new_value

        completed = False
        if goal.target_value and goal.current_value >= goal.target_value:
            if goal.status != "completed":
                goal.status = "completed"
                goal.completed_at = datetime.utcnow()
                completed = True

        await self.db.flush()

        response = {
            "success": True,
            "message": f"Updated '{goal.title}' progress to {new_value}",
            "goal": {
                "title": goal.title,
                "progress": f"{goal.progress_percentage:.0f}%",
                "current_value": goal.current_value,
                "target_value": goal.target_value,
                "status": goal.status
            }
        }

        if completed:
            response["completed"] = f"🎉 Congratulations! You completed '{goal.title}'!"

        return response

    async def _tool_complete_goal(self, goal_title: str) -> Dict[str, Any]:
        """Mark a goal as completed."""
        result = await self.db.execute(
            select(Goal).where(
                Goal.user_id == self.user_id,
                Goal.title.ilike(goal_title)
            )
        )
        goal = result.scalar_one_or_none()

        if not goal:
            return {"success": False, "error": f"Goal '{goal_title}' not found"}

        goal.status = "completed"
        goal.completed_at = datetime.utcnow()
        if goal.target_value:
            goal.current_value = goal.target_value

        await self.db.flush()

        return {
            "success": True,
            "message": f"🎉 Marked '{goal.title}' as completed!"
        }

    async def _tool_delete_goal(self, goal_title: str) -> Dict[str, Any]:
        """Delete a goal."""
        result = await self.db.execute(
            select(Goal).where(
                Goal.user_id == self.user_id,
                Goal.title.ilike(goal_title)
            )
        )
        goal = result.scalar_one_or_none()

        if not goal:
            return {"success": False, "error": f"Goal '{goal_title}' not found"}

        await self.db.delete(goal)
        await self.db.flush()

        return {"success": True, "message": f"Deleted goal '{goal_title}'"}

    # ============ MEMORY/FACT TOOLS ============

    async def _tool_remember_fact(
        self,
        category: str,
        key: str,
        value: str
    ) -> Dict[str, Any]:
        """Remember a fact about the user."""
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.key.ilike(key)
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.value = value
            existing.category = category
            await self.db.flush()
            return {
                "success": True,
                "message": f"Updated fact '{key}' = '{value}'"
            }

        fact = Fact(
            user_id=self.user_id,
            category=category,
            key=key,
            value=value,
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"Remembered: {key} = '{value}'"
        }

    async def _tool_recall_facts(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Recall stored facts."""
        query = select(Fact).where(Fact.user_id == self.user_id)
        if category:
            query = query.where(Fact.category.ilike(category))

        result = await self.db.execute(query)
        facts = result.scalars().all()

        return {
            "success": True,
            "count": len(facts),
            "facts": [
                {
                    "category": f.category,
                    "key": f.key,
                    "value": f.value
                }
                for f in facts
            ]
        }

    async def _tool_forget_fact(self, key: str) -> Dict[str, Any]:
        """Delete a fact."""
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.key.ilike(key)
            )
        )
        fact = result.scalar_one_or_none()

        if not fact:
            return {"success": False, "error": f"Fact '{key}' not found"}

        await self.db.delete(fact)
        await self.db.flush()

        return {"success": True, "message": f"Forgot fact '{key}'"}

    # ============ REMINDERS & TIMERS ============

    async def _tool_set_reminder(
        self,
        message: str,
        when: str,
        priority: str = "medium"
    ) -> Dict[str, Any]:
        """Set a reminder (stored as a fact)."""
        reminder_key = f"reminder_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        fact = Fact(
            user_id=self.user_id,
            category="reminder",
            key=reminder_key,
            value=json.dumps({
                "message": message,
                "when": when,
                "priority": priority,
                "created": datetime.now().isoformat()
            }),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"✅ Reminder set: '{message}' for {when}"
        }

    async def _tool_list_reminders(self) -> Dict[str, Any]:
        """List all reminders."""
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.category == "reminder"
            )
        )
        facts = result.scalars().all()

        reminders = []
        for f in facts:
            try:
                data = json.loads(f.value)
                reminders.append({
                    "id": f.key,
                    "message": data.get("message"),
                    "when": data.get("when"),
                    "priority": data.get("priority")
                })
            except:
                pass

        return {
            "success": True,
            "count": len(reminders),
            "reminders": reminders
        }

    async def _tool_start_timer(
        self,
        label: str,
        duration_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """Start a timer."""
        timer_data = {
            "label": label,
            "started": datetime.now().isoformat(),
            "duration_minutes": duration_minutes
        }

        fact = Fact(
            user_id=self.user_id,
            category="timer",
            key=f"timer_{label.lower().replace(' ', '_')}",
            value=json.dumps(timer_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        if duration_minutes:
            return {
                "success": True,
                "message": f"⏱️ Timer '{label}' started for {duration_minutes} minutes"
            }
        return {
            "success": True,
            "message": f"⏱️ Stopwatch '{label}' started"
        }

    async def _tool_start_pomodoro(self, task: str) -> Dict[str, Any]:
        """Start a Pomodoro session."""
        pomodoro_data = {
            "task": task,
            "started": datetime.now().isoformat(),
            "duration_minutes": 25,
            "type": "work"
        }

        fact = Fact(
            user_id=self.user_id,
            category="pomodoro",
            key="current_pomodoro",
            value=json.dumps(pomodoro_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"🍅 Pomodoro started! Focus on '{task}' for 25 minutes. You've got this!"
        }

    # ============ NOTES & JOURNAL ============

    async def _tool_create_note(
        self,
        content: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a note."""
        note_key = f"note_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        note_data = {
            "title": title or content[:50],
            "content": content,
            "tags": tags or [],
            "created": datetime.now().isoformat()
        }

        fact = Fact(
            user_id=self.user_id,
            category="note",
            key=note_key,
            value=json.dumps(note_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"📝 Note saved: '{title or content[:30]}...'"
        }

    async def _tool_search_notes(
        self,
        query: Optional[str] = None,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search notes."""
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.category == "note"
            )
        )
        facts = result.scalars().all()

        notes = []
        for f in facts:
            try:
                data = json.loads(f.value)
                # Filter by query or tag
                if query and query.lower() not in data.get("content", "").lower():
                    continue
                if tag and tag not in data.get("tags", []):
                    continue
                notes.append({
                    "id": f.key,
                    "title": data.get("title"),
                    "content": data.get("content")[:100],
                    "tags": data.get("tags"),
                    "created": data.get("created")
                })
            except:
                pass

        return {
            "success": True,
            "count": len(notes),
            "notes": notes
        }

    async def _tool_add_journal_entry(
        self,
        content: str,
        mood: Optional[str] = None,
        gratitude: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Add a journal entry."""
        today = date.today().isoformat()
        entry_data = {
            "content": content,
            "mood": mood,
            "gratitude": gratitude or [],
            "timestamp": datetime.now().isoformat()
        }

        fact = Fact(
            user_id=self.user_id,
            category="journal",
            key=f"journal_{today}",
            value=json.dumps(entry_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        response = {"success": True, "message": "📔 Journal entry saved"}
        if mood:
            response["message"] += f" (Mood: {mood})"
        return response

    # ============ HABIT TRACKING ============

    async def _tool_create_habit(
        self,
        name: str,
        frequency: str = "daily",
        target: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a habit."""
        habit_data = {
            "name": name,
            "frequency": frequency,
            "target": target,
            "created": datetime.now().isoformat(),
            "streak": 0,
            "completions": []
        }

        fact = Fact(
            user_id=self.user_id,
            category="habit",
            key=f"habit_{name.lower().replace(' ', '_')}",
            value=json.dumps(habit_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"✨ Habit '{name}' created ({frequency})"
        }

    async def _tool_log_habit(
        self,
        habit_name: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log habit completion."""
        habit_key = f"habit_{habit_name.lower().replace(' ', '_')}"
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.key == habit_key
            )
        )
        fact = result.scalar_one_or_none()

        if not fact:
            return {"success": False, "error": f"Habit '{habit_name}' not found"}

        try:
            data = json.loads(fact.value)
            today = date.today().isoformat()

            if today not in data.get("completions", []):
                data["completions"] = data.get("completions", [])
                data["completions"].append(today)
                data["streak"] = data.get("streak", 0) + 1
                fact.value = json.dumps(data)
                await self.db.flush()

                return {
                    "success": True,
                    "message": f"🔥 '{habit_name}' completed! Streak: {data['streak']} days"
                }
            else:
                return {
                    "success": True,
                    "message": f"'{habit_name}' already logged today"
                }
        except:
            return {"success": False, "error": "Failed to update habit"}

    async def _tool_get_habit_streaks(self) -> Dict[str, Any]:
        """Get all habit streaks."""
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.category == "habit"
            )
        )
        facts = result.scalars().all()

        habits = []
        for f in facts:
            try:
                data = json.loads(f.value)
                habits.append({
                    "name": data.get("name"),
                    "streak": data.get("streak", 0),
                    "frequency": data.get("frequency")
                })
            except:
                pass

        return {
            "success": True,
            "habits": sorted(habits, key=lambda x: x["streak"], reverse=True)
        }

    # ============ HEALTH & WELLNESS ============

    async def _tool_log_water(self, amount_oz: float) -> Dict[str, Any]:
        """Log water intake."""
        today = date.today().isoformat()
        water_key = f"water_{today}"

        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.key == water_key
            )
        )
        fact = result.scalar_one_or_none()

        if fact:
            current = float(fact.value)
            fact.value = str(current + amount_oz)
            total = current + amount_oz
        else:
            fact = Fact(
                user_id=self.user_id,
                category="health",
                key=water_key,
                value=str(amount_oz),
                source="jarvis",
            )
            self.db.add(fact)
            total = amount_oz

        await self.db.flush()

        return {
            "success": True,
            "message": f"💧 Logged {amount_oz}oz water. Total today: {total}oz"
        }

    async def _tool_log_sleep(
        self,
        hours: float,
        quality: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log sleep."""
        today = date.today().isoformat()
        sleep_data = {
            "hours": hours,
            "quality": quality,
            "logged": datetime.now().isoformat()
        }

        fact = Fact(
            user_id=self.user_id,
            category="health",
            key=f"sleep_{today}",
            value=json.dumps(sleep_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        emoji = "😴" if hours >= 7 else "😪"
        return {
            "success": True,
            "message": f"{emoji} Logged {hours} hours of sleep" + (f" ({quality})" if quality else "")
        }

    async def _tool_log_workout(
        self,
        type: str,
        duration_minutes: int,
        intensity: str = "moderate",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log workout."""
        workout_data = {
            "type": type,
            "duration_minutes": duration_minutes,
            "intensity": intensity,
            "notes": notes,
            "timestamp": datetime.now().isoformat()
        }

        fact = Fact(
            user_id=self.user_id,
            category="health",
            key=f"workout_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            value=json.dumps(workout_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"💪 Logged {duration_minutes}min {type} workout ({intensity})"
        }

    async def _tool_log_mood(
        self,
        mood: str,
        notes: Optional[str] = None,
        energy_level: Optional[int] = None
    ) -> Dict[str, Any]:
        """Log mood."""
        mood_data = {
            "mood": mood,
            "notes": notes,
            "energy_level": energy_level,
            "timestamp": datetime.now().isoformat()
        }

        fact = Fact(
            user_id=self.user_id,
            category="health",
            key=f"mood_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            value=json.dumps(mood_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        emoji_map = {
            "ecstatic": "🤩", "happy": "😊", "content": "🙂",
            "neutral": "😐", "sad": "😢", "anxious": "😰",
            "stressed": "😫", "angry": "😠"
        }
        emoji = emoji_map.get(mood, "📊")

        return {
            "success": True,
            "message": f"{emoji} Mood logged: {mood}" + (f" (Energy: {energy_level}/10)" if energy_level else "")
        }

    async def _tool_get_health_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get health summary."""
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.category == "health"
            )
        )
        facts = result.scalars().all()

        summary = {
            "workouts": 0,
            "total_workout_minutes": 0,
            "sleep_entries": 0,
            "avg_sleep": 0,
            "water_days": 0
        }

        sleep_total = 0
        for f in facts:
            if f.key.startswith("workout_"):
                try:
                    data = json.loads(f.value)
                    summary["workouts"] += 1
                    summary["total_workout_minutes"] += data.get("duration_minutes", 0)
                except:
                    pass
            elif f.key.startswith("sleep_"):
                try:
                    data = json.loads(f.value)
                    sleep_total += data.get("hours", 0)
                    summary["sleep_entries"] += 1
                except:
                    pass
            elif f.key.startswith("water_"):
                summary["water_days"] += 1

        if summary["sleep_entries"] > 0:
            summary["avg_sleep"] = round(sleep_total / summary["sleep_entries"], 1)

        return {
            "success": True,
            "summary": summary
        }

    # ============ FINANCE TOOLS ============

    async def _tool_log_expense(
        self,
        amount: float,
        category: str,
        description: Optional[str] = None,
        recurring: bool = False
    ) -> Dict[str, Any]:
        """Log expense."""
        expense_data = {
            "amount": amount,
            "category": category,
            "description": description,
            "recurring": recurring,
            "timestamp": datetime.now().isoformat()
        }

        fact = Fact(
            user_id=self.user_id,
            category="finance_expense",
            key=f"expense_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            value=json.dumps(expense_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"💸 Logged ${amount:.2f} expense ({category})"
        }

    async def _tool_log_income(
        self,
        amount: float,
        source: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log income."""
        income_data = {
            "amount": amount,
            "source": source,
            "description": description,
            "timestamp": datetime.now().isoformat()
        }

        fact = Fact(
            user_id=self.user_id,
            category="finance_income",
            key=f"income_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            value=json.dumps(income_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"💰 Logged ${amount:.2f} income ({source})"
        }

    async def _tool_get_spending_summary(self, period: str = "month") -> Dict[str, Any]:
        """Get spending summary."""
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.category == "finance_expense"
            )
        )
        facts = result.scalars().all()

        by_category = {}
        total = 0
        for f in facts:
            try:
                data = json.loads(f.value)
                cat = data.get("category", "other")
                amt = data.get("amount", 0)
                by_category[cat] = by_category.get(cat, 0) + amt
                total += amt
            except:
                pass

        return {
            "success": True,
            "total": total,
            "by_category": by_category
        }

    async def _tool_set_budget(self, category: str, amount: float) -> Dict[str, Any]:
        """Set a budget."""
        fact = Fact(
            user_id=self.user_id,
            category="budget",
            key=f"budget_{category.lower()}",
            value=str(amount),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"📊 Budget set: ${amount:.2f}/month for {category}"
        }

    # ============ TASK & PROJECT MANAGEMENT ============

    async def _tool_create_task(
        self,
        title: str,
        project: Optional[str] = None,
        priority: str = "medium",
        due_date: Optional[str] = None,
        estimated_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a task."""
        task_data = {
            "title": title,
            "project": project,
            "priority": priority,
            "due_date": due_date,
            "estimated_minutes": estimated_minutes,
            "status": "pending",
            "created": datetime.now().isoformat()
        }

        fact = Fact(
            user_id=self.user_id,
            category="task",
            key=f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            value=json.dumps(task_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"✅ Task created: '{title}'" + (f" (Due: {due_date})" if due_date else "")
        }

    async def _tool_list_tasks(
        self,
        project: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None
    ) -> Dict[str, Any]:
        """List tasks."""
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.category == "task"
            )
        )
        facts = result.scalars().all()

        tasks = []
        for f in facts:
            try:
                data = json.loads(f.value)
                if project and data.get("project") != project:
                    continue
                if status and data.get("status") != status:
                    continue
                if priority and data.get("priority") != priority:
                    continue
                tasks.append({
                    "id": f.key,
                    "title": data.get("title"),
                    "project": data.get("project"),
                    "priority": data.get("priority"),
                    "status": data.get("status"),
                    "due_date": data.get("due_date")
                })
            except:
                pass

        return {
            "success": True,
            "count": len(tasks),
            "tasks": tasks
        }

    async def _tool_complete_task(self, task_title: str) -> Dict[str, Any]:
        """Complete a task."""
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.category == "task"
            )
        )
        facts = result.scalars().all()

        for f in facts:
            try:
                data = json.loads(f.value)
                if data.get("title", "").lower() == task_title.lower():
                    data["status"] = "completed"
                    data["completed_at"] = datetime.now().isoformat()
                    f.value = json.dumps(data)
                    await self.db.flush()
                    return {
                        "success": True,
                        "message": f"✅ Task '{task_title}' completed!"
                    }
            except:
                pass

        return {"success": False, "error": f"Task '{task_title}' not found"}

    async def _tool_create_project(
        self,
        name: str,
        description: Optional[str] = None,
        deadline: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a project."""
        project_data = {
            "name": name,
            "description": description,
            "deadline": deadline,
            "status": "active",
            "created": datetime.now().isoformat()
        }

        fact = Fact(
            user_id=self.user_id,
            category="project",
            key=f"project_{name.lower().replace(' ', '_')}",
            value=json.dumps(project_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"📁 Project '{name}' created"
        }

    # ============ CONTACTS & RELATIONSHIPS ============

    async def _tool_add_contact(
        self,
        name: str,
        relationship: Optional[str] = None,
        notes: Optional[str] = None,
        birthday: Optional[str] = None,
        contact_info: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a contact."""
        contact_data = {
            "name": name,
            "relationship": relationship,
            "notes": notes,
            "birthday": birthday,
            "contact_info": contact_info,
            "created": datetime.now().isoformat(),
            "interactions": []
        }

        fact = Fact(
            user_id=self.user_id,
            category="contact",
            key=f"contact_{name.lower().replace(' ', '_')}",
            value=json.dumps(contact_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"👤 Contact '{name}' added" + (f" ({relationship})" if relationship else "")
        }

    async def _tool_find_contact(self, name: str) -> Dict[str, Any]:
        """Find a contact."""
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.category == "contact"
            )
        )
        facts = result.scalars().all()

        for f in facts:
            try:
                data = json.loads(f.value)
                if name.lower() in data.get("name", "").lower():
                    return {
                        "success": True,
                        "contact": data
                    }
            except:
                pass

        return {"success": False, "error": f"Contact '{name}' not found"}

    async def _tool_log_interaction(
        self,
        contact_name: str,
        type: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log an interaction."""
        contact_key = f"contact_{contact_name.lower().replace(' ', '_')}"
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.key == contact_key
            )
        )
        fact = result.scalar_one_or_none()

        if not fact:
            return {"success": False, "error": f"Contact '{contact_name}' not found"}

        try:
            data = json.loads(fact.value)
            data["interactions"] = data.get("interactions", [])
            data["interactions"].append({
                "type": type,
                "notes": notes,
                "date": datetime.now().isoformat()
            })
            data["last_interaction"] = datetime.now().isoformat()
            fact.value = json.dumps(data)
            await self.db.flush()

            return {
                "success": True,
                "message": f"📝 Logged {type} with {contact_name}"
            }
        except:
            return {"success": False, "error": "Failed to log interaction"}

    # ============ CALENDAR & SCHEDULING ============

    async def _tool_add_event(
        self,
        title: str,
        datetime_str: str,
        duration_minutes: int = 60,
        location: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add calendar event."""
        event_data = {
            "title": title,
            "datetime": datetime_str,
            "duration_minutes": duration_minutes,
            "location": location,
            "description": description
        }

        fact = Fact(
            user_id=self.user_id,
            category="event",
            key=f"event_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            value=json.dumps(event_data),
            source="jarvis",
        )
        self.db.add(fact)
        await self.db.flush()

        return {
            "success": True,
            "message": f"📅 Event added: '{title}' on {datetime_str}"
        }

    async def _tool_get_schedule(
        self,
        date_str: Optional[str] = None,
        days: int = 1
    ) -> Dict[str, Any]:
        """Get schedule."""
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.category == "event"
            )
        )
        facts = result.scalars().all()

        events = []
        for f in facts:
            try:
                data = json.loads(f.value)
                events.append(data)
            except:
                pass

        return {
            "success": True,
            "events": sorted(events, key=lambda x: x.get("datetime", ""))
        }

    async def _tool_get_daily_briefing(self) -> Dict[str, Any]:
        """Get daily briefing."""
        now = datetime.now()
        today = date.today().isoformat()

        # Gather all relevant info
        briefing = {
            "date": now.strftime("%A, %B %d, %Y"),
            "time": now.strftime("%I:%M %p"),
            "events": [],
            "tasks": [],
            "reminders": [],
            "habits_due": [],
            "goals_in_progress": []
        }

        # Get tasks
        tasks_result = await self._tool_list_tasks(status="pending")
        if tasks_result.get("success"):
            briefing["tasks"] = tasks_result.get("tasks", [])[:5]

        # Get goals
        goals_result = await self._tool_list_goals(status="active")
        if goals_result.get("success"):
            briefing["goals_in_progress"] = goals_result.get("goals", [])[:3]

        # Get habits
        habits_result = await self._tool_get_habit_streaks()
        if habits_result.get("success"):
            briefing["habits_due"] = habits_result.get("habits", [])

        return {
            "success": True,
            "briefing": briefing,
            "message": f"Good {self._get_time_of_day()}, Arnav! Here's your briefing for {briefing['date']}"
        }

    def _get_time_of_day(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "morning"
        elif hour < 17:
            return "afternoon"
        else:
            return "evening"

    # ============ UTILITY TOOLS ============

    async def _tool_get_current_datetime(self) -> Dict[str, Any]:
        """Get current date and time."""
        now = datetime.now()
        return {
            "success": True,
            "datetime": now.isoformat(),
            "date": now.strftime("%A, %B %d, %Y"),
            "time": now.strftime("%I:%M %p"),
            "timezone": "local"
        }

    async def _tool_search_memory(self, query: str) -> Dict[str, Any]:
        """Search memory using vector store."""
        if not self.vector_store:
            return {
                "success": False,
                "error": "Memory search not available"
            }

        try:
            results = await self.vector_store.search(
                query=query,
                user_id=str(self.user_id),
                limit=5,
            )
            return {
                "success": True,
                "results": results
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _tool_calculate(self, expression: str) -> Dict[str, Any]:
        """Perform calculations."""
        try:
            # Handle percentages
            expr = re.sub(r'(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)',
                         r'(\1/100)*\2', expression.lower())

            # Safe eval with math functions
            allowed = {
                'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos,
                'tan': math.tan, 'log': math.log, 'log10': math.log10,
                'exp': math.exp, 'pow': pow, 'abs': abs, 'round': round,
                'pi': math.pi, 'e': math.e
            }

            # Remove any non-math characters
            safe_expr = re.sub(r'[^0-9+\-*/().%\s]', '', expr)
            result = eval(safe_expr, {"__builtins__": {}}, allowed)

            return {
                "success": True,
                "expression": expression,
                "result": result
            }
        except Exception as e:
            return {"success": False, "error": f"Calculation error: {str(e)}"}

    async def _tool_convert_units(
        self,
        value: float,
        from_unit: str,
        to_unit: str
    ) -> Dict[str, Any]:
        """Convert units."""
        conversions = {
            # Length
            ("miles", "km"): 1.60934,
            ("km", "miles"): 0.621371,
            ("feet", "meters"): 0.3048,
            ("meters", "feet"): 3.28084,
            ("inches", "cm"): 2.54,
            ("cm", "inches"): 0.393701,
            # Weight
            ("lbs", "kg"): 0.453592,
            ("kg", "lbs"): 2.20462,
            ("oz", "grams"): 28.3495,
            ("grams", "oz"): 0.035274,
            # Temperature (special handling)
            ("c", "f"): lambda c: c * 9/5 + 32,
            ("f", "c"): lambda f: (f - 32) * 5/9,
            # Volume
            ("liters", "gallons"): 0.264172,
            ("gallons", "liters"): 3.78541,
            ("ml", "oz"): 0.033814,
            ("oz", "ml"): 29.5735,
        }

        key = (from_unit.lower(), to_unit.lower())
        if key in conversions:
            factor = conversions[key]
            if callable(factor):
                result = factor(value)
            else:
                result = value * factor

            return {
                "success": True,
                "result": f"{value} {from_unit} = {result:.4f} {to_unit}"
            }

        return {"success": False, "error": f"Unknown conversion: {from_unit} to {to_unit}"}

    async def _tool_get_weather(self, location: Optional[str] = None) -> Dict[str, Any]:
        """Get weather (simulated)."""
        return {
            "success": True,
            "message": "Weather integration coming soon! For now, I'd recommend checking weather.com or your phone's weather app.",
            "note": "This will be connected to a real weather API in a future update."
        }

    async def _tool_web_search(self, query: str) -> Dict[str, Any]:
        """Web search (simulated)."""
        return {
            "success": True,
            "message": f"I noted your search query: '{query}'. Web search integration is coming soon!",
            "suggestion": "For now, you can search this directly on Google or your preferred search engine."
        }

    async def _tool_generate_random(
        self,
        type: str,
        options: Optional[List[str]] = None,
        min: int = 1,
        max: int = 100
    ) -> Dict[str, Any]:
        """Generate random values."""
        import random

        if type == "number":
            result = random.randint(min, max)
            return {"success": True, "result": result}
        elif type == "choice" and options:
            result = random.choice(options)
            return {"success": True, "result": result, "from": options}
        elif type == "coin":
            result = random.choice(["Heads", "Tails"])
            return {"success": True, "result": result}
        elif type == "dice":
            result = random.randint(1, 6)
            return {"success": True, "result": f"🎲 {result}"}

        return {"success": False, "error": "Invalid random type"}

    async def _tool_set_focus_mode(
        self,
        enabled: bool,
        duration_minutes: Optional[int] = None,
        allow_urgent: bool = True
    ) -> Dict[str, Any]:
        """Set focus mode."""
        focus_data = {
            "enabled": enabled,
            "duration_minutes": duration_minutes,
            "allow_urgent": allow_urgent,
            "started": datetime.now().isoformat() if enabled else None
        }

        # Update or create focus mode fact
        result = await self.db.execute(
            select(Fact).where(
                Fact.user_id == self.user_id,
                Fact.key == "focus_mode"
            )
        )
        fact = result.scalar_one_or_none()

        if fact:
            fact.value = json.dumps(focus_data)
        else:
            fact = Fact(
                user_id=self.user_id,
                category="system",
                key="focus_mode",
                value=json.dumps(focus_data),
                source="jarvis",
            )
            self.db.add(fact)

        await self.db.flush()

        if enabled:
            msg = "🎯 Focus mode enabled"
            if duration_minutes:
                msg += f" for {duration_minutes} minutes"
            return {"success": True, "message": msg}
        else:
            return {"success": True, "message": "Focus mode disabled"}
