"""Agent utilities — standalone helpers extracted from agent.py."""
import asyncio
import contextvars
import logging
import random
import subprocess
import traceback
from dataclasses import dataclass
from typing import Callable, Awaitable, Optional

from core.llm.exceptions import LLMError, LLMRateLimitError
from core.constants import MAX_RESPONSE_CHARS, RESPONSE_TRUNCATED_MSG

logger = logging.getLogger(__name__)


class CallCounter:
    """Mutable call counter for tracking LLM invocations across call sites."""
    __slots__ = ("count",)
    def __init__(self):
        self.count = 0


llm_call_counter: contextvars.ContextVar[Optional[CallCounter]] = contextvars.ContextVar("llm_call_counter", default=None)

_RETRY_MAX = 5
_RETRY_BASE_DELAY = 1.0


def _noop(*args, **kwargs):
    pass


@dataclass
class AppCallbacks:
    """Callbacks for TUI integration — replaces direct console I/O."""
    on_chat: Callable[[str], None] = _noop
    on_chunk: Callable[[str], None] = _noop
    on_status: Callable[[str], None] = _noop
    on_tool_start: Callable[[dict, int, int], None] = _noop
    on_result: Callable[[bool, str], None] = _noop
    on_error: Callable[[str], None] = _noop
    on_done: Callable[[float], None] = _noop
    request_approval: Optional[Callable[[str, str], Awaitable[bool]]] = None
    request_plan_approval: Optional[Callable[[str], Awaitable[str]]] = None
    on_iteration: Callable[[int, int], None] = _noop
    on_tool_plan: Callable[[list[dict]], None] = _noop
    on_tokens_used: Callable[..., None] = _noop
    on_plan_created: Callable[[str], None] = _noop


def _create_client(cfg):
    from core.llm import LLMClient
    return LLMClient.from_config(cfg)


async def _call_ai(client, cfg, messages, on_status=None):
    for attempt in range(_RETRY_MAX):
        try:
            counter = llm_call_counter.get()
            if counter is not None:
                counter.count += 1
            response = await client.generate(messages)
            return response.text, response.prompt_tokens, response.completion_tokens, {
                "finish_reason": response.finish_reason,
                "truncated": response.truncated,
            }
        except LLMRateLimitError as e:
            if attempt == _RETRY_MAX - 1:
                raise
            delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1.0)
            if on_status:
                on_status(f"Rate limited. Retry {attempt+1}/{_RETRY_MAX} after {delay:.0f}s...")
            await asyncio.sleep(delay)
        except LLMError:
            raise
        except Exception as e:
            logger.error("Unexpected error in _call_ai: %s\n%s", e, traceback.format_exc())
            raise LLMError(str(e)) from e


async def _call_ai_stream(client, cfg, messages, on_chunk=None, on_status=None):
    """Stream AI response, calling on_chunk(delta) for each chunk."""
    for attempt in range(_RETRY_MAX):
        try:
            counter = llm_call_counter.get()
            if counter is not None:
                counter.count += 1
            text = ""
            prompt_tokens = 0
            completion_tokens = 0
            finish_reason = None
            response_was_truncated = False
            async for chunk in client.generate_stream(messages):
                if chunk.delta:
                    text += chunk.delta
                    if on_chunk:
                        on_chunk(chunk.delta)
                if chunk.prompt_tokens:
                    prompt_tokens = chunk.prompt_tokens
                if chunk.completion_tokens:
                    completion_tokens = chunk.completion_tokens
                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason
                    response_was_truncated = str(finish_reason or "").lower() in {"length", "max_tokens", "model_length"}
            if len(text) > MAX_RESPONSE_CHARS:
                text = text[:MAX_RESPONSE_CHARS] + RESPONSE_TRUNCATED_MSG
                response_was_truncated = True
                finish_reason = finish_reason or "local_max_char_limit"
            return text, prompt_tokens, completion_tokens, {
                "finish_reason": finish_reason,
                "truncated": response_was_truncated,
            }
        except LLMRateLimitError as e:
            if attempt == _RETRY_MAX - 1:
                raise
            delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1.0)
            if on_status:
                on_status(f"Rate limited. Retry {attempt+1}/{_RETRY_MAX} after {delay:.0f}s...")
            await asyncio.sleep(delay)
        except LLMError:
            raise
        except Exception as e:
            logger.error("Unexpected error in _call_ai_stream: %s\n%s", e, traceback.format_exc())
            raise LLMError(str(e)) from e


def _unpack_ai_result(result):
    if len(result) == 3:
        text, prompt_tokens, completion_tokens = result
        return text, prompt_tokens, completion_tokens, {}
    return result


async def run_subprocess(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess without blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: subprocess.run(args, **kwargs))
