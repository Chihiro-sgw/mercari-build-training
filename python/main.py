import os
import logging
import pathlib
import hashlib
from fastapi import FastAPI, Form, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pydantic import BaseModel
from contextlib import asynccontextmanager


# Define the path to the images & sqlite3 database
images = pathlib.Path(__file__).parent.resolve() / "images"
db = pathlib.Path(__file__).parent.resolve() / "db" / "mercari.sqlite3"

# Ensure the images directory exists
images.mkdir(parents=True, exist_ok=True)


def get_db():
    if not db.exists():
        yield

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    try:
        yield conn
    finally:
        conn.close()


# STEP 5-1: set up the database connection
def setup_database():
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_database()
    yield


app = FastAPI(lifespan=lifespan)

logger = logging.getLogger("uvicorn")
logger.level = logging.INFO
images = pathlib.Path(__file__).parent.resolve() / "images"
origins = [os.environ.get("FRONT_URL", "http://localhost:3000")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


class HelloResponse(BaseModel):
    message: str
    category: str = "default"  


@app.get("/", response_model=HelloResponse)
def hello():
    return HelloResponse(**{"message": "Hello, world!"})


class AddItemResponse(BaseModel):
    message: str


# add_item is a handler to add a new item for POST /items .
@app.post("/items", response_model=AddItemResponse)
async def add_item(
    name: str = Form(...),
    category: str = Form(...),
    image: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
):
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not category:
        raise HTTPException(status_code=400, detail="category is required")
    
    # 画像を保存
    image_data = await image.read()
    image_hash = hashlib.sha256(image_data).hexdigest()
    image_name = f"{image_hash}.jpg"
    image_path = images / image_name

    with open(image_path, "wb") as f:
        f.write(image_data)

    insert_item(Item(name=name, category=category, image_name=image_name))
    return AddItemResponse(**{"message": f"item received: {name}"})


@app.get("/items/{item_id}")
def get_items(item_id: int):
    items_file = pathlib.Path(__file__).parent.resolve() / "items.json"
    
    if items_file.exists():
        with open(items_file, "r") as f:
            data = json.load(f)
    else:
        data = {"items": []}
    
    if item_id < 0 or item_id >= len(data["items"]):
        raise HTTPException(status_code=404, detail="Item not found")
    
    return data["items"][item_id]



# get_image is a handler to return an image for GET /images/{filename} .
@app.get("/image/{image_name}")
async def get_image(image_name):
    # Create image path
    image = images / image_name

    if not image_name.endswith(".jpg"):
        raise HTTPException(status_code=400, detail="Image path does not end with .jpg")

    if not image.exists():
        logger.debug(f"Image not found: {image}")
        image = images / "default.jpg"

    return FileResponse(image)


class Item(BaseModel):
    name: str
    category: str
    image_name: str = None


import json

def insert_item(item: Item):

    # STEP 4-1: add an implementation to store an item
    items_file = pathlib.Path(__file__).parent.resolve() / "items.json"
    
    # Load existing items
    if items_file.exists():
        with open(items_file, "r") as f:
            data = json.load(f)
    else:
        data = {"items": []}
    
    # Add new item
    data["items"].append(item.dict())
    
    # Save updated items
    with open(items_file, "w") as f:
        json.dump(data, f, indent=4)
