import os
from datetime import date, datetime
from typing import Literal, Annotated

from fastapi import FastAPI, Request, Form, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import OperationalError

# --- Configuration ---
DATABASE_URL = "sqlite:///data/tasks.db"
TEMPLATES_DIR = "templates"
EMAIL_SIMULATION_LOG_FILE = "data/email_log.txt"

# --- FastAPI App Setup ---
app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- Database Setup ---
Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    priority: Literal["High", "Medium", "Low"] = Column(String)
    due_date = Column(Date)
    completed = Column(Boolean, default=False)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create data directory if it doesn't exist
os.makedirs(os.path.dirname(DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)

# Create tables
Base.metadata.create_all(engine)

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Seed Data ---
def seed_database(db: Session):
    try:
        if db.query(Task).count() == 0:
            print("Seeding database with initial tasks...")
            tasks_to_add = [
                Task(
                    title="Finish FastAPI App",
                    description="Complete all functional and technical requirements.",
                    priority="High",
                    due_date=date.today(),
                    completed=False,
                ),
                Task(
                    title="Buy Groceries",
                    description="Milk, Eggs, Bread, Vegetables",
                    priority="Medium",
                    due_date=date.today(),
                    completed=False,
                ),
                Task(
                    title="Call Mom",
                    description="Wish her a happy birthday.",
                    priority="High",
                    due_date=date.today(),
                    completed=False,
                ),
                Task(
                    title="Plan Weekend Trip",
                    description="Research destinations and activities.",
                    priority="Low",
                    due_date=date(2026, 2, 20),
                    completed=False,
                ),
                Task(
                    title="Workout",
                    description="Go to the gym for an hour.",
                    priority="Medium",
                    due_date=date.today(),
                    completed=True,
                ),
            ]
            db.add_all(tasks_to_add)
            db.commit()
            print("Database seeded successfully.")
    except OperationalError as e:
        print(f"Database seeding error: {e}")
        # This might happen if the database file is locked or corrupted
    except Exception as e:
        print(f"An unexpected error occurred during seeding: {e}")


# Run seeding on startup
@app.on_event("startup")
async def startup_event():
    with SessionLocal() as db:
        seed_database(db)

# --- Routes ---

@app.get("/health", response_class=HTMLResponse)
async def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    high_priority_tasks = db.query(Task).filter(
        Task.due_date == today,
        Task.priority == "High",
        Task.completed == False
    ).all()
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "tasks": high_priority_tasks}
    )

@app.get("/tasks", response_class=HTMLResponse)
async def list_tasks(request: Request, db: Session = Depends(get_db)):
    all_tasks = db.query(Task).order_by(Task.due_date, Task.priority).all()
    return templates.TemplateResponse(
        "tasks.html", {"request": request, "tasks": all_tasks, "date": date.today()}
    )

@app.post("/tasks", response_class=RedirectResponse, status_code=303)
async def create_task(
    request: Request,
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    priority: Annotated[Literal["High", "Medium", "Low"], Form()],
    due_date: Annotated[date, Form()],
    db: Session = Depends(get_db),
):
    new_task = Task(
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        completed=False,
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return RedirectResponse(url="/tasks", status_code=303)

@app.post("/tasks/{task_id}/toggle", response_class=RedirectResponse, status_code=303)
async def toggle_task_completion(
    task_id: int, request: Request, db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.completed = not task.completed
        db.commit()
        db.refresh(task)
    return RedirectResponse(url="/tasks", status_code=303)


async def send_daily_email_summary(pending_tasks: list[Task]):
    summary = f"Daily Task Summary for {date.today()}:\n\n"
    if not pending_tasks:
        summary += "No pending tasks for today!\n"
    else:
        for task in pending_tasks:
            summary += f"- [ ] {task.title} (Priority: {task.priority}, Due: {task.due_date})\n"
    
    # Simulate sending email by logging to console/file
    print("\n" + "=" * 30)
    print("Simulating Daily Email Summary:")
    print(summary)
    print("=" * 30 + "\n")
    
    with open(EMAIL_SIMULATION_LOG_FILE, "a") as f:
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(summary)
        f.write("\n" + "=" * 40 + "\n\n")

@app.post("/simulate-email", response_class=RedirectResponse, status_code=303)
async def trigger_email_summary(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    pending_tasks = db.query(Task).filter(Task.completed == False).all()
    background_tasks.add_task(send_daily_email_summary, pending_tasks)
    
    # Simulate flash message - in a real app, this would use a proper flash messaging system
    print("Flash Message: Daily email summary simulation triggered! Check console/logs.")
    return RedirectResponse(url="/", status_code=303)

# --- Main execution ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
