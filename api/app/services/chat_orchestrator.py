"""Chat orchestration with OpenAI tool calling."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy import desc, select, func
from sqlalchemy.orm import Session

from app.db.models import (
    ApiKey,
    MemoryTypeEnum,
    Persona,
    Reminder,
    ReminderStatusEnum,
    Session as ConversationSession,
    Task,
    User,
    PlanEnum,
)
from app.services.calendar_service import CalendarService
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService
from app.services.metrics_service import MetricsService
from app.services.rate_limiter import RateLimitExceeded, RateLimiter
from app.services.safety import SafetyService, redact_pii
from app.utils.datetime import parse_user_time_to_utc


DEFAULT_PERSONAS: Dict[str, Dict[str, str]] = {
    "coach": {
        "name": "Coach",
        "system_prompt": (
            "You are an upbeat executive coach.\n"
            "- Celebrate progress and reinforce the user's strengths.\n"
            "- Focus on clear next steps, habit formation, and confidence building.\n"
            "- Keep responses structured with short bullets or numbered actions when helpful.\n"
            "- Never make promises outside of the user's control."
        ),
    },
    "calm": {
        "name": "Calm",
        "system_prompt": (
            "You are a grounding, compassionate companion.\n"
            "- Listen carefully and reflect back feelings with warmth.\n"
            "- Offer gentle breathing or mindfulness tips when appropriate.\n"
            "- Encourage seeking trusted humans or professionals for deeper support.\n"
            "- Keep your tone soft, slow, and reassuring."
        ),
    },
    "accountability": {
        "name": "Accountability",
        "system_prompt": (
            "You are a supportive, practical AI life co‑pilot. Your job: (1) listen; (2) extract goals, habits, dates; "
            "(3) act via tools first, then confirm; (4) keep concise, upbeat tone; (5) ask one clarifying question only "
            "when needed; (6) respect safety boundaries; (7) remember personal preferences. Use ISO 8601 datetimes. "
            "Never invent calendar details. End with a one-line next step."
        ),
    },
}


DEFAULT_PERSONA_KEY = "coach"
MEMORY_TOP_K = 5
RECENT_SESSION_LIMIT = 3


@dataclass
class ChatResponse:
    assistant_message: str
    actions: List[Dict[str, Any]]


class PersonaNotFoundError(Exception):
    """Raised when the requested persona does not exist and no default is available."""


class ChatOrchestrator:
    """Coordinate conversational calls with OpenAI and execute tool actions server-side."""

    def __init__(
        self,
        *,
        openai_client,
        embedding_service: EmbeddingService,
        memory_service: MemoryService,
        rate_limiter: RateLimiter,
        metrics_service: MetricsService,
        calendar_service: Optional[CalendarService] = None,
        safety_service: Optional[SafetyService] = None,
        model: str = "gpt-4o-mini",
    ) -> None:
        self._client = openai_client
        self._embedding_service = embedding_service
        self._memory_service = memory_service
        self._rate_limiter = rate_limiter
        self._metrics = metrics_service
        self._calendar_service = calendar_service
        self._safety_service = safety_service
        self._model = model

    def handle_chat(
        self,
        *,
        session: Session,
        api_key: ApiKey,
        message: str,
        persona_key: Optional[str],
    ) -> ChatResponse:
        """Process a chat request and return the assistant response plus executed actions."""

        user = self._get_user(session, api_key.user_id)
        previous_persona = user.current_persona_key
        try:
            self._rate_limiter.check(user.id)
        except RateLimitExceeded as exc:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

        sanitized_message = message.strip() if message else ""
        self._log_user_message(user, sanitized_message)

        if self._safety_service:
            safety_result = self._safety_service.evaluate(sanitized_message)
            if not safety_result.allowed:
                self._metrics.track(
                    "chat_turn",
                    user_id=user.id,
                    properties={
                        "blocked": True,
                        "reason": getattr(safety_result, "reason", None),
                        "persona": previous_persona,
                        "message_length": len(sanitized_message),
                    },
                )
                return ChatResponse(
                    assistant_message=safety_result.response or "I'm unable to help with that.",
                    actions=[],
                )

        persona = self._resolve_persona(session, persona_key)
        persona_changed = (persona.key != previous_persona)
        if persona_changed or user.current_persona_key != persona.key:
            user.current_persona_key = persona.key
            session.add(user)
        memories = self._memory_service.search_memories(
            session,
            user_id=user.id,
            query=sanitized_message,
            top_k=MEMORY_TOP_K,
        )
        recent_sessions = self._recent_sessions(session, user.id)

        system_prompt = self._build_system_prompt(persona.system_prompt, memories, recent_sessions)

        openai_messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sanitized_message},
        ]
        executed_actions: List[Dict[str, Any]] = []

        tools = self._tool_schemas()

        while True:
            response = self._client.create(
                model=self._model,
                messages=openai_messages,
                tools=tools,
                tool_choice="auto",
            )
            choice = response.choices[0]
            assistant_message = choice.message
            assistant_content = assistant_message.content or ""
            tool_calls = getattr(assistant_message, "tool_calls", None) or []

            openai_messages.append(
                {
                    "role": "assistant",
                    "content": assistant_content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                        for tool_call in tool_calls
                    ],
                }
            )

            if tool_calls:
                for tool_call in tool_calls:
                    tool_result, action_record = self._execute_tool(
                        session=session,
                        user=user,
                        tool_name=tool_call.function.name,
                        raw_arguments=tool_call.function.arguments,
                    )
                    executed_actions.append(action_record)
                    openai_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": json.dumps(tool_result),
                        }
                    )
                session.commit()
                continue

            final_message = assistant_content.strip()
            actions_summary = [action["tool"] for action in executed_actions]
            session.add(user)
            session.commit()
            self._metrics.track(
                "chat_turn",
                user_id=user.id,
                properties={
                    "persona": persona.key,
                    "actions": actions_summary,
                    "tool_calls": len(actions_summary),
                    "message_length": len(sanitized_message),
                },
            )
            if persona_changed:
                self._metrics.track(
                    "persona_changed",
                    user_id=user.id,
                    properties={
                        "from": previous_persona,
                        "to": persona.key,
                    },
                )
            return ChatResponse(assistant_message=final_message, actions=executed_actions)

    def _execute_tool(
        self,
        *,
        session: Session,
        user: User,
        tool_name: str,
        raw_arguments: str,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        try:
            arguments = json.loads(raw_arguments or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tool arguments.") from exc

        if tool_name == "schedule_reminder":
            result = self._schedule_reminder(session, user, arguments)
        elif tool_name == "save_memory":
            result = self._save_memory(session, user, arguments)
        elif tool_name == "add_task":
            result = self._add_task(session, user, arguments)
        elif tool_name == "get_agenda":
            result = self._get_agenda(session, user, arguments)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown tool: {tool_name}")

        action_record = {"tool": tool_name, "params": arguments, "result": result}
        return result, action_record

    def _schedule_reminder(self, session: Session, user: User, arguments: Dict[str, Any]) -> Dict[str, Any]:
        text = arguments.get("text")
        run_ts_raw = arguments.get("run_ts")

        if not text or not run_ts_raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reminder requires text and run_ts.")

        if user.plan == PlanEnum.FREE:
            today = datetime.now(timezone.utc)
            start_of_day = today.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            existing_count = (
                session.query(func.count(Reminder.id))
                .filter(
                    Reminder.user_id == user.id,
                    Reminder.run_ts >= start_of_day,
                    Reminder.run_ts < end_of_day,
                    Reminder.status != ReminderStatusEnum.FAILED,
                )
                .scalar()
                or 0
            )
            if existing_count >= 5:
                raise HTTPException(status_code=402, detail="Upgrade to Pro to schedule more reminders today.")

        try:
            run_ts = parse_user_time_to_utc(run_ts_raw)
        except ValueError:
            run_ts = self._parse_datetime(run_ts_raw)
        reminder = Reminder(
            user_id=user.id,
            text=text,
            run_ts=run_ts,
        )
        session.add(reminder)
        session.flush()
        self._metrics.track(
            "reminder_created",
            user_id=user.id,
            properties={
                "run_ts": reminder.run_ts.isoformat(),
                "source": "chat_tool",
            },
        )
        return {
            "id": str(reminder.id),
            "text": reminder.text,
            "run_ts": reminder.run_ts.isoformat(),
        }

    def _save_memory(self, session: Session, user: User, arguments: Dict[str, Any]) -> Dict[str, Any]:
        memory_type_value = arguments.get("type")
        text = arguments.get("text")
        if not memory_type_value or not text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Memory requires type and text.")

        try:
            memory_type = MemoryTypeEnum(memory_type_value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid memory type.") from exc

        memory = self._memory_service.save_memory(
            session,
            user_id=user.id,
            memory_type=memory_type,
            text=text,
            source=None,
        )
        session.flush()
        return {
            "id": str(memory.id),
            "type": memory.type.value,
            "text": memory.text,
        }

    def _add_task(self, session: Session, user: User, arguments: Dict[str, Any]) -> Dict[str, Any]:
        title = arguments.get("title")
        due_ts_raw = arguments.get("due_ts")
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task requires a title.")

        due_ts = self._parse_datetime(due_ts_raw) if due_ts_raw else None
        task = Task(
            user_id=user.id,
            title=title,
            due_ts=due_ts,
        )
        session.add(task)
        session.flush()

        calendar_event = None
        if self._calendar_service and due_ts and user.plan == PlanEnum.PRO:
            calendar_event = self._calendar_service.sync_task_event(user, task, due_ts=due_ts)
            session.flush()

        return {
            "id": str(task.id),
            "title": task.title,
            "due_ts": task.due_ts.isoformat() if task.due_ts else None,
            "calendar_event": {
                "id": calendar_event.get("id"),
                "htmlLink": calendar_event.get("htmlLink"),
            } if calendar_event else None,
        }

    def _get_agenda(self, session: Session, user: User, arguments: Dict[str, Any]) -> Dict[str, Any]:
        start_raw = arguments.get("from")
        end_raw = arguments.get("to")
        if user.plan != PlanEnum.PRO:
            raise HTTPException(status_code=402, detail="Upgrade to Pro to access the calendar.")
        now = datetime.now(timezone.utc)
        start = self._parse_datetime(start_raw) if start_raw else now
        end = self._parse_datetime(end_raw) if end_raw else start + timedelta(days=7)
        if end < start:
            end = start + timedelta(days=1)

        query = (
            select(Task)
            .where(Task.user_id == user.id)
            .where(Task.due_ts.is_not(None))
            .where(Task.due_ts >= start)
            .where(Task.due_ts <= end)
            .order_by(Task.due_ts.asc())
        )

        tasks = session.execute(query).scalars().all()
        events = []
        if self._calendar_service:
            events = self._calendar_service.list_events(user, start=start, end=end, limit=5)

        return {
            "tasks": [
                {
                    "id": str(task.id),
                    "title": task.title,
                    "due_ts": task.due_ts.isoformat() if task.due_ts else None,
                    "calendar_event_id": task.linked_calendar_event_id,
                }
                for task in tasks
            ],
            "events": events,
        }

    def _get_user(self, session: Session, user_id: uuid.UUID) -> User:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
        return user

    def _resolve_persona(self, session: Session, persona_key: Optional[str]) -> Persona:
        key = (persona_key or DEFAULT_PERSONA_KEY).lower()
        default_config = DEFAULT_PERSONAS.get(key)
        persona = session.execute(select(Persona).where(Persona.key == key)).scalar_one_or_none()
        if persona:
            if (
                default_config
                and (
                    persona.system_prompt != default_config["system_prompt"]
                    or persona.name != default_config["name"]
                )
            ):
                persona.system_prompt = default_config["system_prompt"]
                persona.name = default_config["name"]
                session.add(persona)
                session.flush()
            return persona

        if not default_config:
            raise PersonaNotFoundError(f"Persona '{key}' is not available.")

        persona = Persona(
            key=key,
            name=default_config["name"],
            system_prompt=default_config["system_prompt"],
        )
        session.add(persona)
        session.flush()
        return persona

    def _recent_sessions(self, session: Session, user_id: uuid.UUID) -> List[ConversationSession]:
        query = (
            select(ConversationSession)
            .where(ConversationSession.user_id == user_id)
            .order_by(desc(ConversationSession.created_at))
            .limit(RECENT_SESSION_LIMIT)
        )
        return session.execute(query).scalars().all()

    def _build_system_prompt(
        self,
        persona_prompt: str,
        memories: Iterable,
        sessions: Iterable[ConversationSession],
    ) -> str:
        context_segments: List[str] = []

        memory_lines = [
            f"- ({memory.type.value}) {memory.text}" for memory in memories
        ]
        if memory_lines:
            context_segments.append("Relevant memories:\n" + "\n".join(memory_lines))

        session_lines: List[str] = []
        for session_record in sessions:
            transcript = session_record.transcript
            if isinstance(transcript, list):
                transcript_text = " ".join(str(item) for item in transcript)
            elif isinstance(transcript, dict):
                transcript_text = json.dumps(transcript)
            else:
                transcript_text = str(transcript)
            session_lines.append(f"- {transcript_text}")
        if session_lines:
            context_segments.append("Recent sessions:\n" + "\n".join(session_lines))

        context_block = "\n\n".join(context_segments) if context_segments else "No additional context."

        tools_description = (
            "You can call these tools when helpful:\n"
            "1. schedule_reminder(text, run_ts)\n"
            "2. save_memory(type, text)\n"
            "3. add_task(title, due_ts)\n"
            "4. get_agenda(from, to)"
        )

        base_instructions = (
            "You are the AI Companion assistant. "
            "Follow the persona guidelines below. "
            "Call tools when they improve the user's outcome, and confirm completion after using them."
        )

        return "\n\n".join(
            [
                base_instructions,
                tools_description,
                f"Persona instructions:\n{persona_prompt.strip()}",
                f"Context:\n{context_block}",
            ]
        )

    def _tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "schedule_reminder",
                    "description": "Schedule a reminder for the user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Reminder text to deliver."},
                            "run_ts": {
                                "type": "string",
                                "description": "ISO 8601 timestamp when the reminder should trigger.",
                            },
                        },
                        "required": ["text", "run_ts"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_memory",
                    "description": "Store an important detail about the user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [enum.value for enum in MemoryTypeEnum],
                            },
                            "text": {"type": "string", "description": "The memory content."},
                        },
                        "required": ["type", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_task",
                    "description": "Create a task for the user to follow up on.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Task title or description."},
                            "due_ts": {
                                "type": "string",
                                "description": "Optional ISO 8601 due date for the task.",
                            },
                        },
                        "required": ["title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_agenda",
                    "description": "Fetch upcoming items for the user's agenda.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from": {
                                "type": "string",
                                "description": "Start of the time range (ISO 8601).",
                            },
                            "to": {
                                "type": "string",
                                "description": "End of the time range (ISO 8601).",
                            },
                        },
                    },
                },
            },
        ]

    def _log_user_message(self, user: User, message: str) -> None:
        if message:
            logger.info("Received message from user {}: {}", user.id, redact_pii(message))

    @staticmethod
    def _parse_datetime(raw_value: str) -> datetime:
        if raw_value is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing datetime value.")
        value = raw_value.strip()
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid datetime format.") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
