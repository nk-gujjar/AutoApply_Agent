# Project Structure And Architecture

This document explains:

- Current architecture and request flow
- Directory and file structure
- `.env` parameter format (no secrets)
- `personal.txt` sample format via separate `sample.txt` file

## 1) Request And Agent Architecture

### Entry points

- FastAPI app: `backend/server.py` and `backend/api/app.py`
- Streamlit UI: `frontend/chat_frontend.py`
- CLI helper query: `scripts/run_backend_query.sh`

### Runtime flow

1. Query reaches `/chat` in `backend/api/chat_routes.py`.
2. `ClientAgent` (`modules/multi_agent/client_agent.py`) handles orchestration.
3. `LLMRouter` (`modules/multi_agent/llm_router.py`) classifies intent and payload.
4. `A2ACoordinator` (`modules/multi_agent/a2a.py`) dispatches to selected agent(s).
5. Agent implementations under `modules/multi_agent/agents/` execute domain logic.
6. Domain logic in `modules/core/` performs scraping/apply/CV operations.
7. Response is summarized and returned to API/UI.

### Agent catalog and routing metadata

- Config file: `modules/multi_agent/config/agent_catalog.yaml`
- Loaded by: `modules/multi_agent/agent_catalog.py`
- Controls:
  - Agent class path
  - Routing hints
  - Allowed payload keys
  - Default payload values
  - A2A intent names

### Current major agents

- `telegram_scraper`
- `naukri_scraper`
- `fetch_jobs`
- `jd_extractor`
- `resume_rewrite`
- `naukri_applier`
- `external_applier`

## 2) Directory Structure

High-level tree (important paths only):

```text
AutoApply_Agent/
  backend/
    server.py
    api/
      app.py
      chat_routes.py
      a2a_routes.py
      schemas.py
      state.py

  frontend/
    chat_frontend.py

  modules/
    core/
      appliers/
      config/
      cv/
      forms/
      profile/
      scrapers/
    multi_agent/
      agents/
      config/
      tools/
      a2a.py
      agent_catalog.py
      client_agent.py
      llm_router.py
      models.py

  scripts/
    run_backend_server.sh
    run_backend_query.sh
    run_frontend.sh
    run_full_stack.sh

  templates/
    cv_template.tex
    cv_template1.tex
    base_cv.txt

  data/
    jobs/
    memory/
    other/

  logs/
    autoapply.log

  output/
    *.tex, generated resume artifacts

  files/
    archi_diagram.png

  personal.txt
  requirements.txt
  README.md
```

## 3) Key File Details

### Root level files

- `README.md`: Primary setup, run commands, API list, and architecture summary.
- `sample.txt`: Parameter-only template you can copy into `personal.txt`.
- `personal.txt`: Your real profile data used for resume tailoring and form filling.
- `.env`: Runtime configuration for API keys, Telegram, Naukri, and app settings.
- `requirements.txt`: Python dependency list.
- `main.py`: CLI-style entry script for selected workflows/modes.
- `telegramJobScrapper.py`: Standalone Telegram scrape runner for channel-based fetches.

### Backend API files

- `backend/server.py`: Uvicorn import target; creates app via `create_app()`.
- `backend/api/app.py`: Registers and mounts API routers.
- `backend/api/chat_routes.py`: `/chat`, `/chat/debug`, `/health`, and resume artifact endpoints.
- `backend/api/a2a_routes.py`: A2A protocol endpoints (`agent-card`, `message:send`, task APIs).
- `backend/api/schemas.py`: Pydantic request/response models.
- `backend/api/state.py`: Session and chat state helpers (memory/context helpers).

### Multi-agent orchestration files

- `modules/multi_agent/client_agent.py`: Main orchestrator, routing execution, summary generation.
- `modules/multi_agent/llm_router.py`: Intent parsing and payload extraction.
- `modules/multi_agent/a2a.py`: A2A coordinator and local transport contracts.
- `modules/multi_agent/agent_catalog.py`: Loads agent metadata from YAML catalog.
- `modules/multi_agent/models.py`: Shared internal data models.
- `modules/multi_agent/config/agent_catalog.yaml`: Agent definitions, defaults, allowed keys, intent names.
- `modules/multi_agent/agents/*.py`: Agent implementations (scrape, fetch, extract, rewrite, apply).
- `modules/multi_agent/tools/io_tools.py`: Helper I/O tools for loading/saving structured workspace data.

### Core domain files

- `modules/core/config/settings.py`: Environment loading, config validation, logger setup, Groq LLM factory.
- `modules/core/scrapers/`: Naukri/Telegram/fetch scraping logic.
- `modules/core/appliers/`: Naukri Easy Apply and external apply automations.
- `modules/core/cv/cv_engine.py`: Resume/CV tailoring and generation engine.
- `modules/core/forms/`: Form fill support utilities.
- `modules/core/profile/`: Profile parsing and profile-model handling.

### Scripts

- `scripts/run_backend_server.sh`: Starts backend server only.
- `scripts/run_frontend.sh`: Starts Streamlit frontend only.
- `scripts/run_full_stack.sh`: Starts backend + frontend workflow.
- `scripts/run_backend_query.sh`: Sends one terminal query to backend.

### Data and artifacts

- `data/jobs/`: Scraped jobs and apply outcomes (`applied`, `failed`, `skipped`).
- `data/memory/`: Persisted session memory snapshots.
- `data/other/`: Auxiliary runtime files (metadata, trackers, intermediate files).
- `logs/autoapply.log`: Main application log file.
- `output/`: Generated resume/CV artifacts and intermediate outputs.
- `files/archi_diagram.png`: Architecture image used in README.

## 4) `.env` Parameter Format (No Values)

Use this as a safe template:

```dotenv
# Telegram API Configuration
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
BOT_TOKEN=
PHONE_NUMBER=
TELEGRAM_SESSION_NAME=

# AI API Configuration
GEMINI_API_KEY=
GROQ_API_KEY=

# LLM Provider Configuration
LLM_PROVIDER=groq
GROQ_MODEL=groq/compound
DEFAULT_LLM_MODEL=groq/compound

# Email Configuration (Optional)
EMAIL_USER=
EMAIL_PASSWORD=
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Naukri.com Credentials
NAUKRI_EMAIL=
NAUKRI_PASSWORD=

# Job Search Configuration
TARGET_ROLES=SDE,Software Engineer,Agentic AI,AI Engineer
MIN_EXPERIENCE=0
MAX_EXPERIENCE=5
MIN_CTC=10
TARGET_CHANNELS=@channel1,@channel2

# Application Settings
MAX_APPLICATIONS_PER_DAY=10
DELAY_BETWEEN_APPLICATIONS=300
AUTO_APPLY=false
```

## 5) `personal.txt` Sample Format

Use the dedicated template file:

- `sample.txt`

Copy it and populate values in `personal.txt`.

## 6) Operational Notes

- Logs: `logs/autoapply.log`
- Job/result data: `data/jobs/`
- Memory files: `data/memory/`
- Resume outputs: `output/`
- Architecture image used in README: `files/archi_diagram.png`