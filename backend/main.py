# main.py
import base64
import json
from asyncio import sleep as asleep
from datetime import datetime

import anthropic
import httpx
from fastapi import Depends, FastAPI, HTTPException
from loguru import logger
from redis import Redis
from rq import Queue
from sqlmodel import Field, Session, SQLModel, create_engine, select


# Database model
class FoodEntry(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: int
    timestamp: datetime
    meal_name: str
    calories: float
    protein: float
    carbs: float
    fat: float


# Database setup
DATABASE_URL = "sqlite:///./calorie_counter.db"
engine = create_engine(DATABASE_URL)

SQLModel.metadata.create_all(engine)

# Redis and RQ setup
redis_conn = Redis(host="redis", port=6379)
q = Queue(connection=redis_conn)

client = anthropic.Anthropic()

app = FastAPI()


# Dependency to get the database session
def get_session():
    with Session(engine) as session:
        yield session


# Helper function to analyze image using Claude 3.5
def analyze_image_with_claude(image_url):
    logger.info("Start analysis")
    logger.info(f"Image URL: {image_url}")
    start = datetime.now()
    media_type = "image/jpeg"
    image_data = base64.b64encode(httpx.get(image_url).content).decode("utf-8")
    message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": """
Provide a calorie estimate for this meal in kcal. Also, specify the macronutrient content of the meal in percentages.
Reply in JSON format with the following keys: 'meal_name', 'calories', 'protein', 'carbs', 'fat'.
DO NOT REPLY ANYTHING ELSE THAN JSON. Do your best to provide a good estimation.""",
                    },
                ],
            }
        ],
    )
    logger.info(f"End analysis. Took {(datetime.now() - start).total_seconds():.2f} s")
    return json.loads(message.content[0].text)


# Endpoint to upload an image and get calorie/macro information
@app.post("/meal", response_model=FoodEntry)
async def analyze_image(
    photo_url: str, user_id: int = 1, session: Session = Depends(get_session)
):
    # Enqueue the task to analyze the image
    job = q.enqueue(analyze_image_with_claude, photo_url)
    # Wait for the job to finish
    while not job.result:
        await asleep(0.1)
    result = job.result

    if result is None:
        raise HTTPException(status_code=500, detail="Image analysis failed")

    meal_name = result["meal_name"]
    calories = round(result["calories"])
    carbs = round(calories * (result["carbs"] / 100) / 4)
    fat = round(calories * (result["fat"] / 100) / 9)
    protein = round(calories * (result["protein"] / 100) / 4)

    # Create a new FoodEntry
    new_entry = FoodEntry(
        user_id=user_id,
        timestamp=datetime.now(),
        meal_name=meal_name,
        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat,
    )
    session.add(new_entry)
    session.commit()

    session.refresh(new_entry)

    return new_entry


# Endpoint to get daily status
@app.get("/daily_status/{user_id}")
def get_daily_status(user_id: int, session: Session = Depends(get_session)):
    today = datetime.now().date()
    entries = session.exec(
        select(FoodEntry).where(
            (FoodEntry.user_id == user_id) & (FoodEntry.timestamp >= today)
        )
    ).all()

    total_calories = sum(entry.calories for entry in entries)
    total_protein = sum(entry.protein for entry in entries)
    total_carbs = sum(entry.carbs for entry in entries)
    total_fat = sum(entry.fat for entry in entries)

    return {
        "calories": total_calories,
        "protein": total_protein,
        "carbs": total_carbs,
        "fat": total_fat,
    }


# Endpoint to get time charts data
@app.get("/time_charts/{user_id}")
def get_time_charts(
    user_id: int, days: int = 7, session: Session = Depends(get_session)
):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    entries = session.exec(
        select(FoodEntry)
        .where(
            (FoodEntry.user_id == user_id)
            & (FoodEntry.timestamp >= start_date)
            & (FoodEntry.timestamp <= end_date)
        )
        .order_by(FoodEntry.timestamp)
    ).all()

    chart_data = [
        {
            "date": entry.timestamp.date().isoformat(),
            "calories": entry.calories,
            "protein": entry.protein,
            "carbs": entry.carbs,
            "fat": entry.fat,
        }
        for entry in entries
    ]

    return chart_data
