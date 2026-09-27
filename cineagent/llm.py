import os
import json
import requests
from dotenv import load_dotenv
import tools

load_dotenv()

openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
model = "liquid/lfm-2.5-2.6b:free"
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

def ask_openrouter(prompt: str, system_context: str = "", chat_id: str = None, enable_tools: bool = False) -> str:
    if not openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set.")

    messages = []
    if system_context:
        messages.append({"role": "system", "content": system_context})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages
    }
    
    if enable_tools:
        payload["tools"] = tools.TOOLS_SCHEMA

    try:
        # Step 1: Initial call to OpenRouter
        response = requests.post(
            openrouter_url,
            json=payload,
            headers={"Authorization": f"Bearer {openrouter_api_key}"},
            timeout=60,
        )
        response.raise_for_status()
        res_json = response.json()
        message_data = res_json["choices"][0]["message"]

        # Step 2: Check if LLM requested a Tool Call
        if "tool_calls" in message_data and message_data["tool_calls"]:
            messages.append(message_data)

            for tool_call in message_data["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                raw_args = tool_call["function"].get("arguments", "{}")
                try:
                    fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    fn_args = {}

                tool_output = tools.execute_tool_call(tool_name, fn_args, chat_id=chat_id)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": tool_output
                })

            # Step 3: Follow-up request with tool results
            second_response = requests.post(
                openrouter_url,
                json={"model": model, "messages": messages},
                headers={"Authorization": f"Bearer {openrouter_api_key}"},
                timeout=60,
            )
            second_response.raise_for_status()
            content = second_response.json()["choices"][0]["message"]["content"]
        else:
            content = message_data.get("content", "")

        if not content:
            raise ValueError("The AI service returned an empty response")
        return content

    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        print(f"Agent Loop Error: {exc}")
        raise RuntimeError("The movie assistant is temporarily unavailable. Please try again.") from exc
