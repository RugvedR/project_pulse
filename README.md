# 🫀 Project Pulse — Agentic Expense Orchestrator

> A future-proof, agentic financial companion that moves beyond passive tracking to active, context-aware financial reasoning.

## What Is Pulse?

Pulse is an AI-powered financial management system built on **LangGraph**. It receives natural-language expense inputs via a **Telegram bot**, uses **Gemini Flash** to parse and reason about them, stores validated transactions in **Supabase (PostgreSQL)**, and proactively coaches you with weekly financial briefings and a real-time analytics dashboard.

## Architecture

```
Telegram → Scribe (Parse) → Router (Decide) → Vault (Save to DB)
                                  ↓
                          Investigator (Web Search)
                                  ↓
                            Coach (Weekly Briefing)
                                  ↓
                        Dashboard (Streamlit Analytics)
```

## Tech Stack

| Layer           | Technology                          |
|-----------------|-------------------------------------|
| Orchestration   | LangGraph (stateful, cyclic graphs) |
| Intelligence    | Gemini 3.1 Flash (Google AI Studio) |
| Interface       | Telegram Bot API (`python-telegram-bot`) |
| Analytics       | Streamlit (Real-time Dashboard)      |
| Database        | Supabase / PostgreSQL (SQLAlchemy 2.0) |
| Deployment      | Docker + Hugging Face Spaces        |
| Environment     | Python 3.11                         |

## Quick Start

```bash
# 1. Clone and enter project
cd project_pulse

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 5. Run the bot
python main.py
```

## Development Phases

- **Phase 1** ✅ Foundation — Parse & Save (The Scribe)
- **Phase 2** ✅ Agentic Reasoning — Research & Route (The Investigator)
- **Phase 3** ✅ Proactive Insights — Weekly Briefing (The Coach)
- **Phase 4** ✅ Universal Protocol — MCP & LLM Factory
- **Phase 5** 🚀 Advanced Intelligence — Visualization & Multi-Currency (Roadmap)

## Universal Access (MCP)

Pulse now supports the **Model Context Protocol (MCP)**. This means any MCP-compatible AI agent (like Claude Desktop) can use your Pulse tools.

To run the MCP server:
```bash
python -m pulse.mcp_server
```

To test the server locally:
```bash
python test_mcp_locally.py
```

## Project Structure

```
project_pulse/
├── pulse/              # Main application package
│   ├── config.py       # Centralized settings
│   ├── state.py        # AgentState TypedDict
│   ├── graph.py        # LangGraph assembly
│   ├── nodes/          # LangGraph nodes (scribe, vault, router, etc.)
│   ├── tools/          # LangChain tools (db, search)
│   ├── db/             # SQLAlchemy models & CRUD
│   ├── schemas/        # Pydantic data contracts
│   └── bot/            # Telegram handlers & scheduling
├── data/               # SQLite databases (gitignored)
├── tests/              # Unit & integration tests
└── notebooks/          # Prototyping notebooks
```

## License

Private — All rights reserved.
