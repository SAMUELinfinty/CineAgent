# 🎬 CineAgent

> A personal AI-powered Telegram movie & series assistant built to explore agentic AI, tool calling, state management, and LLM orchestration.

CineAgent is a Telegram-based personal movie assistant powered by an LLM.

The goal is to move beyond a simple chatbot and build an agent that can **understand a user's request, decide what action is required, use tools, maintain state, and return useful results.**

---

## 🚀 Project Goal

CineAgent is being built as a practical way to learn and implement:

- LLM integration
- Agent orchestration
- Tool calling
- State management
- Telegram bot development
- API integration
- Structured data handling
- Multi-step interactions

The project is intentionally being built from the fundamentals rather than relying on an agent framework from the beginning.

---

## 🧠 How CineAgent Works

The long-term architecture looks like this:

```text
                    ┌──────────────┐
                    │    User      │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Telegram   │
                    │     Bot      │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │     Agent    │
                    │ Orchestrator │
                    └──────┬───────┘
                           │
                  ┌────────┴────────┐
                  ▼                 ▼
           ┌────────────┐    ┌────────────┐
           │    LLM     │    │   Tools    │
           │  OpenRouter│    │            │
           └────────────┘    └─────┬──────┘
                                   │
                           ┌───────┴────────┐
                           ▼                ▼
                    ┌────────────┐   ┌─────────────┐
                    │ Watchlist  │   │ Other Tools │
                    │    CSV     │   │   Future    │
                    └────────────┘   └─────────────┘
