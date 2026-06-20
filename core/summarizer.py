"""Chat history summarization - prevents context window overflow."""

import json
from typing import Optional

from rich.console import Console

console = Console()

SUMMARY_PROMPT = """*Briefly* summarize this partial conversation about programming.
Include less detail about older parts and more detail about the most recent messages.
Start a new paragraph every time the topic changes!

This is only part of a longer conversation so *DO NOT* conclude the summary with language like "Finally, ...". Because the conversation continues after the summary.
The summary *MUST* include the function names, libraries, packages that are being discussed.
The summary *MUST* include the filenames that are being referenced by the assistant inside the ```...``` fenced code blocks!
The summaries *MUST NOT* include ```...``` fenced code blocks!

Phrase the summary with the USER in first person, telling the ASSISTANT about the conversation.
Write *as* the user.
The user should refer to the assistant as *you*.
Start the summary with "I asked you...".

Keep summaries under 150 words.
Weight the last 3-5 messages: 70% detail, older messages: 30% detail.
Example output:
"I asked you how to optimize pandas queries. You suggested..."
"""


class ChatSummarizer:
    """Summarizes chat history to keep context window manageable."""

    def __init__(self, model_name: str = None, max_tokens: int = 100_000):
        self.model_name = model_name
        self.max_tokens = max_tokens

    def token_count(self, messages: list[dict]) -> int:
        """Estimate token count. Rough: ~4 chars per token."""
        text = json.dumps(messages)
        return len(text) // 3

    def too_big(self, messages: list[dict]) -> bool:
        """Check if messages exceed the max token budget."""
        return self.token_count(messages) > self.max_tokens

    def summarize(self, messages: list[dict], client=None) -> list[dict]:
        """
        Summarize messages if they're too big.
        Keeps the last few messages intact, summarizes the rest.
        Always uses text summarization (no AI call) for speed.
        """
        if not self.too_big(messages):
            return messages

        # Keep last 2 exchanges (4 messages: user+assistant x2)
        if len(messages) > 4:
            keep = messages[-4:]
            summarize = messages[:-4]
        else:
            # Too few messages to split, just trim from front
            target = self.max_tokens
            result = []
            for msg in reversed(messages):
                tokens = self.token_count([msg])
                if tokens <= target:
                    result.insert(0, msg)
                    target -= tokens
                else:
                    break
            return result

        # Simple text summary (fast, no AI call)
        summary_text = self._simple_summary(summarize)
        return [
            {"role": "user", "content": f"(Previous context: {summary_text})"},
        ] + keep

    def _simple_summary(self, messages: list[dict]) -> str:
        """Create a simple text summary without AI."""
        parts = []
        for msg in messages[-8:]:  # Last 8 messages
            role = msg["role"].upper()
            content = msg.get("content", "")
            # Truncate long content
            if len(content) > 200:
                content = content[:200] + "..."
            parts.append(f"[{role}] {content}")
        return " | ".join(parts)

    def _ask_ai_for_summary(self, messages: list[dict], client) -> Optional[str]:
        """Ask AI to summarize messages."""
        try:
            content = ""
            for msg in messages:
                role = msg["role"].upper()
                text = msg.get("content", "")
                if role in ("USER", "ASSISTANT") and text:
                    content += f"# {role}\n{text}\n"

            response = client.chat.completions.create(
                model=self.model_name or "deepseek-chat",
                messages=[
                    {"role": "system", "content": SUMMARY_PROMPT},
                    {"role": "user", "content": content},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e:
            console.print(f"[dim]Summarization failed: {e}[/dim]")
            return None