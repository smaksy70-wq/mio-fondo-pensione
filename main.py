from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests
import os
from utils import extract_costs_from_pdf, get_covip_funds, USER_AGENT, COVIP_BENCHMARKS
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/api/funds")
def list_funds(q: str = None):
    try:
        all_funds = get_covip_funds()
        if not q: return all_funds
        q_lower = q.lower()
        return [f for f in all_funds if q_lower in f['name'].lower() or q_lower in f['albo'].lower()]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
@app.get("/api/analyze")
def analyze_fund(url: str = Query(...), type: str = Query("FPN")):
    try:
        data = extract_costs_from_pdf(url)
        data["benchmarks_10y"] = {
            "FPN": COVIP_BENCHMARKS["FPN"][2],
            "FPA": COVIP_BENCHMARKS["FPA"][2],
            "PIP": COVIP_BENCHMARKS["PIP"][2]
        }
        return data
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
