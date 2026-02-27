"""
High School Management System API

A FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
Activity and participant data is persisted in a SQLite database.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from pathlib import Path
from typing import Optional
from sqlmodel import Field, Session, SQLModel, create_engine, select

# ---------------------------------------------------------------------------
# Database models
# ---------------------------------------------------------------------------

class Activity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str
    schedule: str
    max_participants: int


class Participant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str
    activity_name: str = Field(foreign_key="activity.name")


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

current_dir = Path(__file__).parent
DATABASE_URL = f"sqlite:///{current_dir}/database.db"
engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


# Seed data – only inserted when the activities table is empty
SEED_ACTIVITIES = [
    {"name": "Chess Club", "description": "Learn strategies and compete in chess tournaments",
     "schedule": "Fridays, 3:30 PM - 5:00 PM", "max_participants": 12,
     "participants": ["michael@mergington.edu", "daniel@mergington.edu"]},
    {"name": "Programming Class", "description": "Learn programming fundamentals and build software projects",
     "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM", "max_participants": 20,
     "participants": ["emma@mergington.edu", "sophia@mergington.edu"]},
    {"name": "Gym Class", "description": "Physical education and sports activities",
     "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM", "max_participants": 30,
     "participants": ["john@mergington.edu", "olivia@mergington.edu"]},
    {"name": "Soccer Team", "description": "Join the school soccer team and compete in matches",
     "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM", "max_participants": 22,
     "participants": ["liam@mergington.edu", "noah@mergington.edu"]},
    {"name": "Basketball Team", "description": "Practice and play basketball with the school team",
     "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM", "max_participants": 15,
     "participants": ["ava@mergington.edu", "mia@mergington.edu"]},
    {"name": "Art Club", "description": "Explore your creativity through painting and drawing",
     "schedule": "Thursdays, 3:30 PM - 5:00 PM", "max_participants": 15,
     "participants": ["amelia@mergington.edu", "harper@mergington.edu"]},
    {"name": "Drama Club", "description": "Act, direct, and produce plays and performances",
     "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM", "max_participants": 20,
     "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]},
    {"name": "Math Club", "description": "Solve challenging problems and participate in math competitions",
     "schedule": "Tuesdays, 3:30 PM - 4:30 PM", "max_participants": 10,
     "participants": ["james@mergington.edu", "benjamin@mergington.edu"]},
    {"name": "Debate Team", "description": "Develop public speaking and argumentation skills",
     "schedule": "Fridays, 4:00 PM - 5:30 PM", "max_participants": 12,
     "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]},
]


def seed_database():
    with Session(engine) as session:
        existing = session.exec(select(Activity)).first()
        if existing:
            return  # Already seeded
        for data in SEED_ACTIVITIES:
            activity = Activity(
                name=data["name"],
                description=data["description"],
                schedule=data["schedule"],
                max_participants=data["max_participants"],
            )
            session.add(activity)
            session.flush()  # so activity.name is available
            for email in data["participants"]:
                session.add(Participant(email=email, activity_name=activity.name))
        session.commit()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "static")), name="static")


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    seed_database()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _activity_to_dict(activity: Activity, participants: list[str]) -> dict:
    return {
        "description": activity.description,
        "schedule": activity.schedule,
        "max_participants": activity.max_participants,
        "participants": participants,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    with Session(engine) as session:
        activities = session.exec(select(Activity)).all()
        result = {}
        for activity in activities:
            participants = session.exec(
                select(Participant).where(Participant.activity_name == activity.name)
            ).all()
            result[activity.name] = _activity_to_dict(
                activity, [p.email for p in participants]
            )
        return result


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    with Session(engine) as session:
        # Validate activity exists
        activity = session.exec(
            select(Activity).where(Activity.name == activity_name)
        ).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        # Validate student is not already signed up
        existing = session.exec(
            select(Participant).where(
                Participant.activity_name == activity_name,
                Participant.email == email
            )
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Student is already signed up")

        # Validate capacity
        participant_count = len(session.exec(
            select(Participant).where(Participant.activity_name == activity_name)
        ).all())
        if participant_count >= activity.max_participants:
            raise HTTPException(status_code=400, detail="Activity is full")

        # Add student
        session.add(Participant(email=email, activity_name=activity_name))
        session.commit()
        return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    with Session(engine) as session:
        # Validate activity exists
        activity = session.exec(
            select(Activity).where(Activity.name == activity_name)
        ).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        # Find the participant record
        participant = session.exec(
            select(Participant).where(
                Participant.activity_name == activity_name,
                Participant.email == email
            )
        ).first()
        if not participant:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity"
            )

        # Remove student
        session.delete(participant)
        session.commit()
        return {"message": f"Unregistered {email} from {activity_name}"}
