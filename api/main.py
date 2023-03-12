import json
import logging
from typing import Literal

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api import schemas
from db import database, crud
from utils import scrap

logging.basicConfig(format="%(levelname)s::%(asctime)s - %(message)s", datefmt="%d-%b-%y %H:%M:%S", level=logging.INFO)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="resources"), name="static")
TEMPLATES = Jinja2Templates(directory="resources")

with open("resources/manifest.json") as file:
    manifest = json.load(file)

with open("config.json") as file:
    config = json.load(file)

real_debrid_token = None
if "real_debrid" in config:
    real_debrid_client_id = config["real_debrid"]["client_id"]
    real_debrid_client_secret = config["real_debrid"]["client_secret"]
    real_debrid_username = config["real_debrid"]["username"]
    real_debrid_password = config["real_debrid"]["password"]
    real_debrid_token_url = "https://api.real-debrid.com/oauth/v2/token"

    data = {
        "grant_type": "password",
        "client_id": real_debrid_client_id,
        "client_secret": real_debrid_client_secret,
        "username": real_debrid_username,
        "password": real_debrid_password
    }

    response = requests.post(real_debrid_token_url, data=data)
    if response.status_code == 200:
        real_debrid_token = response.json()["access_token"]
    else:
        logging.warning(f"Failed to get Real Debrid access token: {response.content}")

@app.on_event("startup")
async def init_db():
    await database.init()


@app.on_event("startup")
async def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scrap.run_schedule_scrape, CronTrigger(hour="*/3"))
    scheduler.start()
    app.state.scheduler = scheduler


@app.on_event("shutdown")
async def stop_scheduler():
    app.state.scheduler.shutdown(wait=False)


@app.get("/")
async def get_home(request: Request):
    return TEMPLATES.TemplateResponse(
        "home.html",
        {
            "request": request,
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "description": manifest.get("description"),
            "gives": [
                "Tamil Movies & Series",
                "Malayalam Movies & Series",
                "Telugu Movies & Series",
                "Hindi Movies & Series",
                "Kannada Movies & Series",
                "English Movies & Series",
                "Dubbed Movies & Series",
            ],
            "logo": "static/tamilblasters.png",
        },
    )


@app.get("/manifest.json")
async def get_manifest(response: Response):
    response.headers.update({"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*"})
    return manifest


@app.get("/catalog/movie/{catalog_id}.json", response_model=schemas.Movie)
@app.get("/catalog/movie/{catalog_id}/skip={skip}.json", response_model=schemas.Movie)
@app.get("/catalog/series/{catalog_id}.json", response_model
