# SmartAccident — Setup Guide

Complete setup instructions for running the SmartAccident platform locally on **Linux** and **Windows**.

---

## Prerequisites

Ensure the following are installed on your system before proceeding:

| Tool | Version | Purpose |
|---|---|---|
| **Git** | 2.x+ | Version control |
| **Docker** | 24.x+ | Container runtime |
| **Docker Compose** | v2.x+ (included with Docker Desktop) | Multi-container orchestration |
| **Python** | 3.12+ | Backend runtime |
| **Node.js** | 20.x+ LTS | Frontend runtime |
| **npm** | 10.x+ | Node package manager |

---

## 1. Clone the Repository

```bash
git clone https://github.com/Auxilus08/HackByte4.0.git
cd HackByte4.0
```

---

## 2. Environment Configuration

Create a `.env` file in the project root by copying the example:

### Linux / macOS

```bash
cp .env.example .env
```

### Windows (PowerShell)

```powershell
Copy-Item .env.example .env
```

### Windows (CMD)

```cmd
copy .env.example .env
```

Then edit `.env` and fill in the required values:

```dotenv
# ─── Database ──────────────────────────────────
POSTGRES_USER=smartaccident
POSTGRES_PASSWORD=smartaccident_secret
POSTGRES_DB=smartaccident_db

# ─── App ───────────────────────────────────────
SECRET_KEY=change_me_in_production

# ─── Trello API (get from https://trello.com/power-ups/admin) ───
TRELLO_API_KEY=
TRELLO_API_TOKEN=
TRELLO_WEBHOOK_SECRET=

# ─── Google Maps Geocoding API ─────────────────
GOOGLE_MAPS_API_KEY=

# ─── Blockchain (Polygon) ─────────────────────
WEB3_PROVIDER_URL=
REWARD_CONTRACT_ADDRESS=
DEPLOYER_PRIVATE_KEY=
```

> **Note:** For initial development, only the database credentials are required. API keys can be added later.

---

## 3. Start the Database (Docker)

The PostgreSQL + PostGIS database runs in a Docker container.

### Linux / macOS

```bash
# Start the database service in detached mode
docker compose up db -d

# Verify it's running and healthy
docker compose ps
```

### Windows (PowerShell / CMD)

```powershell
# Start the database service in detached mode
docker compose up db -d

# Verify it's running and healthy
docker compose ps
```

> **Expected output:** The `smartaccident_db` container should show status `Up (healthy)`.

### Verify PostGIS Extensions

```bash
docker exec smartaccident_db psql -U smartaccident -d smartaccident_db -c "\dx"
```

You should see `postgis`, `postgis_topology`, `fuzzystrmatch`, and `postgis_tiger_geocoder`.

---

## 4. Backend Setup

### Linux / macOS

```bash
# Navigate to backend directory
cd backend

# Create a Python virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
pip install sqlalchemy geoalchemy2 psycopg2-binary asyncpg shapely numpy
pip install fastapi uvicorn alembic pydantic

# Run database migrations
alembic upgrade head

# Verify migration
alembic current
# Expected output: 31a717b2606a (head)
```

### Windows (PowerShell)

```powershell
# Navigate to backend directory
cd backend

# Create a Python virtual environment
python -m venv venv

# Activate the virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install sqlalchemy geoalchemy2 psycopg2-binary asyncpg shapely numpy
pip install fastapi uvicorn alembic pydantic

# Run database migrations
alembic upgrade head

# Verify migration
alembic current
# Expected output: 31a717b2606a (head)
```

### Windows (CMD)

```cmd
cd backend
python -m venv venv
.\venv\Scripts\activate.bat

pip install sqlalchemy geoalchemy2 psycopg2-binary asyncpg shapely numpy
pip install fastapi uvicorn alembic pydantic

alembic upgrade head
alembic current
```

> **Windows Note:** If `psycopg2-binary` fails to install, you may need to install the [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/). Alternatively, use `psycopg2-binary` which provides pre-built wheels for Windows.

### Verify Database Tables

```bash
docker exec smartaccident_db psql -U smartaccident -d smartaccident_db -c "\dt public.*"
```

Expected tables: `accidents`, `volunteers`, `tasks`, `alembic_version`, `spatial_ref_sys`.

---

## 5. Frontend Setup (Coming Soon)

The frontend is not yet scaffolded. Once available:

### Linux / macOS

```bash
cd frontend
npm install
npm run dev
```

### Windows (PowerShell / CMD)

```powershell
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`.

---

## 6. Running the Full Stack with Docker Compose

Once all services have Dockerfiles, you can start everything at once:

```bash
# From the project root
docker compose up -d

# Check status of all services
docker compose ps

# View logs
docker compose logs -f
```

| Service | URL | Description |
|---|---|---|
| **Database** | `localhost:5432` | PostgreSQL + PostGIS |
| **Backend** | `http://localhost:8000` | FastAPI server |
| **Frontend** | `http://localhost:3000` | Next.js dashboard |

---

## Common Commands Reference

### Database

```bash
# Start database only
docker compose up db -d

# Stop database
docker compose stop db

# View database logs
docker compose logs db -f

# Connect to PostgreSQL shell
docker exec -it smartaccident_db psql -U smartaccident -d smartaccident_db

# Reset database (CAUTION: deletes all data)
docker compose down -v
docker compose up db -d
```

### Alembic (Migrations)

```bash
# Apply all pending migrations
alembic upgrade head

# Show current migration version
alembic current

# Show migration history
alembic history

# Generate a new migration after model changes
alembic revision --autogenerate -m "describe_your_change"

# Rollback last migration
alembic downgrade -1

# Rollback all migrations
alembic downgrade base
```

### Backend (once main.py is set up)

```bash
# Start the FastAPI dev server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# API docs will be at:
# http://localhost:8000/docs      (Swagger UI)
# http://localhost:8000/redoc     (ReDoc)
```

---

## Troubleshooting

### Docker Issues

| Problem | Solution |
|---|---|
| `port 5432 already in use` | Stop any local PostgreSQL: `sudo systemctl stop postgresql` (Linux) or stop the PostgreSQL service in Windows Services |
| `docker compose` not found | Upgrade Docker Desktop to latest version, or install `docker-compose-plugin` |
| Container keeps restarting | Check logs: `docker compose logs db` |

### Python / pip Issues

| Problem | Solution |
|---|---|
| `psycopg2` build fails (Windows) | Use `pip install psycopg2-binary` instead |
| `ModuleNotFoundError` | Make sure the venv is activated: `source venv/bin/activate` (Linux) or `.\venv\Scripts\Activate.ps1` (Windows) |
| Wrong Python version | Verify with `python --version`, needs 3.12+ |

### Alembic Issues

| Problem | Solution |
|---|---|
| `Connection refused` on migration | Ensure Docker DB is running: `docker compose ps` |
| `DuplicateTableError` | Tables already exist. Drop and re-migrate: `alembic downgrade base && alembic upgrade head` |
| `Target database is not up to date` | Run `alembic upgrade head` first |

### Windows-Specific

| Problem | Solution |
|---|---|
| `venv\Scripts\Activate.ps1` blocked | Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` in PowerShell as Admin |
| Line ending issues | Run `git config core.autocrlf true` before cloning |
| Docker Desktop not starting | Enable WSL2 and Hyper-V in Windows Features |

---

## Project Structure

```
HackByte4.0/
├── backend/
│   ├── alembic/                # Database migration scripts
│   │   ├── versions/           # Migration files
│   │   └── env.py              # Alembic environment config
│   ├── src/
│   │   ├── models/             # SQLAlchemy ORM models
│   │   │   ├── accident.py     # Accident model (PostGIS POINT)
│   │   │   ├── volunteer.py    # Volunteer model (PostGIS POINT)
│   │   │   ├── task.py         # Task assignment model
│   │   │   └── base.py         # Declarative base
│   │   ├── config/             # Settings & database config (coming)
│   │   ├── controllers/        # Request handlers (coming)
│   │   ├── routes/             # API routes (coming)
│   │   ├── services/           # Business logic (coming)
│   │   └── main.py             # FastAPI app entry point (coming)
│   ├── alembic.ini             # Alembic configuration
│   └── venv/                   # Python virtual environment (gitignored)
├── frontend/                   # Next.js app (coming)
├── ml-model/                   # ML criticality model (coming)
├── blockchain/                 # Smart contracts (coming)
├── scripts/
│   └── init-postgis.sql        # PostGIS extension initialization
├── docker-compose.yml          # Docker service definitions
├── .env.example                # Environment variable template
├── .gitignore
├── README.md
└── SETUP.md                    # ← You are here
```
