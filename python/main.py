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

    conn = sqlite3.connect(db,check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    try:
        yield conn
    finally:
        conn.close()


# STEP 5-1: set up the database connection
def setup_database():
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            image_name TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

def get_category_id(db_conn: sqlite3.Connection, category_name: str) -> int:
    cursor = db_conn.cursor()
    
    # 既存のカテゴリがあるか確認
    cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
    category = cursor.fetchone()

    if category:
        return category["id"]

    # 新しいカテゴリを追加
    cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
    db_conn.commit()
    
    return cursor.lastrowid


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

    category_id = get_category_id(db, category)

    insert_item(Item(name=name, category_id=category_id, image_name=image_name), db)

    return AddItemResponse(**{"message": f"item received: {name}"})

@app.get("/items")
def get_items(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute('''
        SELECT items.id, items.name, categories.name AS category, items.image_name 
        FROM items
        JOIN categories ON items.category_id = categories.id
    ''')
    items = cursor.fetchall()
    return {"items": [dict(item) for item in items]}

@app.get("/items/{item_id}")
def get_item(item_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute('SELECT name, category, image_name FROM items WHERE id = ?', (item_id,))
    item = cursor.fetchone()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return dict(item)



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

@app.get("/search")
def search_items(keyword: str, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    query = "SELECT name, category, image_name FROM items WHERE name LIKE ?"
    cursor.execute(query, (f"%{keyword}%",))
    items = cursor.fetchall()
    return {"items": [dict(item) for item in items]}

class Item(BaseModel):
    name: str
    category_id: int
    image_name: str = None



def insert_item(item: Item, db_conn: sqlite3.Connection):
    cursor = db_conn.cursor()
    cursor.execute('''
        INSERT INTO items (name, category_id, image_name) VALUES (?, ?, ?)
    ''', (item.name, item.category_id, item.image_name))
    db_conn.commit()
