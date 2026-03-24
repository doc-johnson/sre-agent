import json
import logging
from collections.abc import Generator

from openai import OpenAI

from app.config import (
    MAX_ITERATIONS,
    MAX_TOOL_CALLS_PER_ITERATION,
    PROVIDERS,
    SYSTEM_PROMPT,
)
from app.tools import TOOL_DEFINITIONS, TOOL_HANDLERS

logger = logging.getLogger(__name__)

_llm_clients: dict[str, OpenAI] = {}
_current_provider: str = ""
_current_model: str = ""


def set_provider(provider: str, model: str | None = None) -> None:
    global _current_provider, _current_model
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    _current_provider = provider
    cfg = PROVIDERS[provider]
    _current_model = model if model and model in cfg["models"] else cfg["default_model"]


def _get_llm() -> tuple[OpenAI, str]:
    if _current_provider not in _llm_clients:
        cfg = PROVIDERS[_current_provider]
        _llm_clients[_current_provider] = OpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
        )
    return _llm_clients[_current_provider], _current_model


def investigate(alert: str) -> Generator[dict, None, None]:
    client, model = _get_llm()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Investigate this alert: {alert}"},
    ]

    for iteration in range(MAX_ITERATIONS):
        logger.info(f"Iteration {iteration + 1}/{MAX_ITERATIONS}")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                temperature=0,
            )
        except Exception as e:
            yield {"type": "error", "content": f"LLM error: {e}"}
            return

        choice = response.choices[0]
        message = choice.message

        if message.content:
            if choice.finish_reason == "stop" or not message.tool_calls:
                yield {"type": "conclusion", "content": message.content}
                messages.append({"role": "assistant", "content": message.content})
                break
            else:
                yield {"type": "thought", "content": message.content}

        if not message.tool_calls:
            if message.content:
                break
            yield {"type": "error", "content": "Agent produced empty response"}
            return

        messages.append(_msg_to_dict(message))

        tool_calls = message.tool_calls[:MAX_TOOL_CALLS_PER_ITERATION]

        for tc in tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                fn_args = {}

            yield {
                "type": "tool_call",
                "tool": fn_name,
                "arguments": fn_args,
                "call_id": tc.id,
            }

            handler = TOOL_HANDLERS.get(fn_name)
            if not handler:
                result = {"success": False, "error": f"Unknown tool: {fn_name}"}
            else:
                try:
                    result = handler(fn_args)
                except Exception as e:
                    result = {"success": False, "error": str(e)[:500]}

            result_str = json.dumps(result, default=str)
            if len(result_str) > 4000:
                result_str = result_str[:4000] + '..."}'

            yield {
                "type": "tool_result",
                "tool": fn_name,
                "result": result,
                "call_id": tc.id,
            }

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })
    else:
        yield {
            "type": "conclusion",
            "content": "Investigation reached maximum iterations. Review the evidence collected above to form a conclusion.",
        }

    yield {"type": "done"}


def _msg_to_dict(message) -> dict:
    msg = {"role": "assistant", "content": message.content or ""}
    if message.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ]
    return msg
