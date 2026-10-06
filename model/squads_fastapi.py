from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import re

# Path to the JSON file
squads = "../data/processed/datewise_squad.json"

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allows your frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Load squads data at startup
with open(squads, 'r') as file:
    squads_data = json.load(file)


@app.post("/squads")
def get_squads(request_data: dict):
    # Extract data from request body
    Date = request_data.get('Date')

    # Validation
    if not Date:
        raise HTTPException(status_code=400, detail="Missing query parameter")

    date = Date

    # Check if the date is in YYYY-MM-DD format
    if not re.match(r'\d{4}-\d{2}-\d{2}', date):
        raise HTTPException(status_code=400, detail="Fill Date in YYYY-MM-DD format")

    if date in squads_data:
        # Check if the player exists in the data
        leagues = squads_data.get(date)
        if leagues:
            return leagues
        else:
            raise HTTPException(status_code=404, detail="No Leagues Available")
    else:
        raise HTTPException(status_code=404, detail="No Data Available")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=3001)