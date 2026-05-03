# Project Specification: Pulse Agentic Expense Orchestrator

**Vision:** A future-proof, agentic financial companion that moves beyond passive tracking to active, context-aware financial reasoning.

---

## 1. Executive Summary
The Pulse Orchestrator is an AI-powered financial management system that leverages **LangGraph** to manage stateful, cyclic workflows. Unlike traditional expense trackers that rely on rigid if-then logic, Pulse uses a **ReAct (Reason + Act)** pattern to handle messy real-world data, perform autonomous research on unknown transactions, and provide proactive financial coaching. The system is built on a "Universal Protocol" philosophy, ensuring that it remains model-agnostic and ready for the **Model Context Protocol (MCP)** ecosystem.

---

## 2. System Architecture & How It Works
The system operates as a **State Machine**. Each user interaction triggers a graph traversal where data is passed between specialized "Nodes."

### The Core Agentic Loop
*   **Entry Node (The Scribe):** Receives raw text/images from Telegram. It uses an LLM to extract structured data (amount, currency, vendor).
*   **Logic Node (The Router):** Evaluates the data. If a vendor is unrecognized, it routes to the Research Node. If information is complete, it routes to the Tool Node.
*   **Research Node (The Investigator):** Uses a Search Tool (Tavily/Serper) to identify unknown merchants and suggest a category.
*   **Action Node (The Vault):** Executes a Python tool to write the validated transaction to the SQLite database.
*   **Review Node (The Coach):** Periodically analyzes the state of the database to provide proactive insights (e.g., "You're approaching your hobby budget limit for May").

---

## 3. Tech Stack (Zero-Cost & Professional)
*   **Orchestration:** LangGraph (for state management and cyclic loops).
*   **Intelligence:** Gemini 3.0 Flash (Free Tier via Google AI Studio).
*   **Interface:** Telegram Bot API (via `python-telegram-bot`).
*   **Schema & Validation:** Pydantic (to ensure strict JSON data structures).
*   **Database:** SQLAlchemy + SQLite (Local, lightweight, and professional).
*   **Environment:** Python 3.11+.

---

## 4. Development Phases

### Phase 1: Foundations (The "Scribe" MVP)
*   Set up Telegram Bot and SQLite schema.
*   Implement a linear LangGraph: `Input -> Parse -> Save`.
*   Integrate Gemini Flash to handle messy natural language (e.g., "Spent 450 at the badminton court").

### Phase 2: Agentic Reasoning (The "Investigator")
*   Introduce **Conditional Edges** in LangGraph.
*   Develop a **Web Search Tool**. If the LLM doesn't recognize a vendor, it must search the web before categorizing.
*   Implement **Self-Correction**: If the Database Tool returns an error, the agent must "think" and fix the entry.

### Phase 3: Proactive Insights (The "Coach")
*   Create a cron-job node that runs every 7 days.
*   The agent retrieves the last week's data and identifies "Spending Anomalies" or "Budget Alerts."
*   Send a proactive "Weekly Briefing" to the user via Telegram.

### Phase 4: The Universal Protocol (Future-Proofing)
*   **MCP Integration:** Refactor Python tools into an MCP Server. This allows any LLM (Claude, Llama 3 via Ollama, etc.) to use your expense tools without a rewrite.
*   **Local Migration:** Test swapping Gemini for a local model (Ollama) to ensure privacy for sensitive financial data.

---

## 5. Future-Ready Context for Implementation
To ensure a professional coding strategy:
*   **Stateful Memory:** Every transaction must carry a `thread_id`. This allows the user to say "Actually, change that last one to 500" and the agent will know which entry to update.
*   **Tool-First Design:** Never let the LLM "hallucinate" a database entry. All writes must go through a documented Pydantic-validated tool.
*   **Model Agnostic:** All LLM calls must use the **LangChain-Google-GenAI** abstraction so the model provider can be changed in a single config file.
*   **Human-in-the-loop (HITL):** For large or "Unusual" expenses, the graph should enter a `WAIT` state and ask the user for a "Confirm/Deny" click in Telegram before writing to the DB.

---

## 6. Project Prerequisites
*   Google AI Studio API Key.
*   Telegram Bot Token (from @BotFather).
*   Python Libraries: `langgraph`, `langchain-google-genai`, `sqlalchemy`, `python-telegram-bot`, `pydantic`.
