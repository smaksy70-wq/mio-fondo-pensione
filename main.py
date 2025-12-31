from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from utils import extract_costs_from_pdf, get_covip_funds, USER_AGENT
import requests
import os

app = FastAPI()

@app.get("/api/funds")
def list_funds(q: str = None):
    """
    Returns lists of funds. Fetches fresh data from COVIP every time to ensure up-to-date information.
    """
    print("Fetching fresh fund list from COVIP...")
    # Fetch all funds fresh
    all_funds = get_covip_funds()
    
    if not q:
        return all_funds
    
    q_lower = q.lower()
    # Filter the fresh list
    return [
        f for f in all_funds 
        if q_lower in f['name'].lower() or q_lower in f['albo'].lower()
    ]

@app.get("/api/analyze")
def analyze_fund(
    url: str = Query(..., description="URL"), 
    type: str = Query("FPN", description="Type"),
    albo: str = Query(None, description="Albo"),
    name: str = Query(None, description="Name")
):
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    data = extract_costs_from_pdf(url)
    
    # Add benchmark data based on type
    # Default to FPN if unknown
    bench_key = "FPA" if "aperte" in type.lower() or "FPA" in type else "FPN"
    # Logic to refine:
    # If type is "FPA", use FPA. If "FPN", use FPN.
    # COVIP codes: FPN=Negoziale, FPA=Aperto, PIP=PIP.
    if "FPA" in type: bench_key = "FPA"
    elif "PIP" in type: bench_key = "PIP"
    else: bench_key = "FPN"
    
    from utils import COVIP_BENCHMARKS, get_fund_returns
    # Return all 10-year benchmarks for the chart
    # FPN index 2 (10 years), FPA index 2, PIP index 2
    data["benchmarks_10y"] = {
        "FPN": COVIP_BENCHMARKS["FPN"][2],
        "FPA": COVIP_BENCHMARKS["FPA"][2],
        "PIP": COVIP_BENCHMARKS["PIP"][2]
    }
    
    # NEW: Fetch Historical Returns
    
    return data
    
@app.get("/api/proxy_pdf")
def proxy_pdf(url: str = Query(..., description="PDF URL")):
    try:
        # Fetch the PDF
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, verify=False, stream=True)
        response.raise_for_status()
        
        # Stream it back with inline disposition
        def iterfile():
            yield from response.iter_content(chunk_size=8192)
            
        headers = {
            "Content-Disposition": "inline; filename=scheda_costi.pdf",
            "Content-Type": "application/pdf"
        }
        
        return StreamingResponse(iterfile(), headers=headers)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
def get_pdf(url: str = Query(...)):
    """
    Proxy to download the PDF avoiding CORS or direct link issues if necessary.
    Actually COVIP links are public, so frontend can just link to them.
    But we can provide a convenience wrapper if needed.
    """
    pass

# Mount static files (Frontend)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
