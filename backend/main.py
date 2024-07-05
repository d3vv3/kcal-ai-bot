# main.py
from asyncio import sleep as asleep
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from sqlmodel import Field, Session, SQLModel, create_engine, select
from rq import Queue
from redis import Redis
from datetime import datetime
from time import sleep
import os
from typing import List
from loguru import logger

# Database model
class FoodEntry(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: int
    timestamp: datetime
    calories: float
    protein: float
    carbs: float
    fat: float

# Database setup
DATABASE_URL = "sqlite:///./calorie_counter.db"
engine = create_engine(DATABASE_URL)

SQLModel.metadata.create_all(engine)

# Redis and RQ setup
redis_conn = Redis(host='redis', port=6379)
q = Queue(connection=redis_conn)

app = FastAPI()

# Dependency to get the database session
def get_session():
    with Session(engine) as session:
        yield session

# Helper function to analyze image using Claude 3.5 (mocked for this example)
def analyze_image_with_claude(image_data):
    logger.info("Start analysis")
    start = datetime.now()
    # In a real implementation, you would send the image to Claude 3.5 for analysis
    # For this example, we'll return mock data
    sleep(1)
    logger.info(f"End analysis. Took {(datetime.now() - start).total_seconds():.2f} s")
    return {
        "calories": 500,
        "protein": 20,
        "carbs": 60,
        "fat": 15
    }

# Endpoint to upload an image and get calorie/macro information
@app.post("/upload_image")
async def upload_image(file: UploadFile = File(...), user_id: int = 1, session: Session = Depends(get_session)):
    contents = await file.read()
    
    # Enqueue the task to analyze the image
    job = q.enqueue(analyze_image_with_claude, contents)
    # Wait for the job to finish
    while not job.result:
        await asleep(0.1)
    result = job.result

    if result is None:
        raise HTTPException(status_code=500, detail="Image analysis failed")

    # Create a new FoodEntry
    new_entry = FoodEntry(
        user_id=user_id,
        timestamp=datetime.now(),
        calories=result["calories"],
        protein=result["protein"],
        carbs=result["carbs"],
        fat=result["fat"]
    )
    session.add(new_entry)
    session.commit()

    return result

# Endpoint to get daily status
@app.get("/daily_status/{user_id}")
def get_daily_status(user_id: int, session: Session = Depends(get_session)):
    today = datetime.now().date()
    entries = session.exec(
        select(FoodEntry).where(
            (FoodEntry.user_id == user_id) &
            (FoodEntry.timestamp >= today)
        )
    ).all()

    total_calories = sum(entry.calories for entry in entries)
    total_protein = sum(entry.protein for entry in entries)
    total_carbs = sum(entry.carbs for entry in entries)
    total_fat = sum(entry.fat for entry in entries)

    return {
        "total_calories": total_calories,
        "total_protein": total_protein,
        "total_carbs": total_carbs,
        "total_fat": total_fat
    }

# Endpoint to get time charts data
@app.get("/time_charts/{user_id}")
def get_time_charts(user_id: int, days: int = 7, session: Session = Depends(get_session)):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    entries = session.exec(
        select(FoodEntry).where(
            (FoodEntry.user_id == user_id) &
            (FoodEntry.timestamp >= start_date) &
            (FoodEntry.timestamp <= end_date)
        ).order_by(FoodEntry.timestamp)
    ).all()

    chart_data = [
        {
            "date": entry.timestamp.date().isoformat(),
            "calories": entry.calories,
            "protein": entry.protein,
            "carbs": entry.carbs,
            "fat": entry.fat
        }
        for entry in entries
    ]

    return chart_data
