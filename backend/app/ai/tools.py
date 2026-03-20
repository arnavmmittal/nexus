"""Tools that Jarvis can use to interact with user data and systems."""
from __future__ import annotations

import json
from datetime import datetime, date
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
        # Check if skill exists
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

        # Log the XP
        xp_log = SkillXPLog(
            skill_id=skill.id,
            xp_amount=xp_amount,
            source="jarvis",
            description=description,
        )
        self.db.add(xp_log)

        # Update skill
        skill.current_xp += xp_amount
        skill.total_xp += xp_amount
        skill.last_practiced = datetime.utcnow()

        # Check for level up
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
        # Check if goal exists
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

        # Log progress
        progress_log = GoalProgressLog(
            goal_id=goal.id,
            previous_value=goal.current_value,
            new_value=new_value,
        )
        self.db.add(progress_log)

        goal.current_value = new_value

        # Check if completed
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
        # Check if fact exists (update if so)
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
