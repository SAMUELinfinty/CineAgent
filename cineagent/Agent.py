import json
from State import state
import tools
from llm import ask_openrouter

def run_agent(prompt: str, chat_id: str | int) -> str:
    """Orchestrates the Agentic Loop: UNDERSTAND -> DECIDE -> ACT -> OBSERVE -> RESPOND."""
    # 1. Fetch user context from State
    current_movie = state.get_current_movie(chat_id)
    system_context = f"The user is currently discussing the movie: {current_movie}." if current_movie else ""

    # 2. Call ask_openrouter with tools enabled
    response = ask_openrouter(
        prompt=prompt,
        system_context=system_context,
        chat_id=str(chat_id),
        enable_tools=True
    )
    return response

if __name__ == "__main__":
    # Test the agent orchestrator locally!
    test_chat_id = "7685127918"
    print("Testing Agent Orchestrator...")
    answer = run_agent("Search my watchlist for Primal Fear", chat_id=test_chat_id)
    print("\n--- Agent Response ---")
    print(answer)
