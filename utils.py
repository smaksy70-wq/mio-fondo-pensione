
import requests
import re
import io
import os
import hashlib
import traceback
from bs4 import BeautifulSoup
import pdfplumber
import pandas as pd

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Benchmarks hardcoded for display
# Source: COVIP Relazione Annuale (Approximate averages)
# Years: 2, 5, 10, 35
# Format: List [2y, 5y, 10y, 35y]
COVIP_BENCHMARKS = {
    "FPN": [1.0, 0.6, 0.4, 0.3],   
    "FPA": [2.2, 1.4, 1.1, 1.0],   
    "PIP": [3.7, 2.8, 2.4, 1.9]   
}

def get_covip_funds():
    url = "https://www.covip.it/per-gli-operatori/fondi-pensione/costi-e-rendimenti-dei-fondi-pensione/elenco-schede-costi"
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table', id='datatable-1')
        
        funds = []
        if table:
            tbody = table.find('tbody')
            for row in tbody.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 4:
                    albo = cols[0].get_text(strip=True)
                    name = cols[1].get_text(strip=True)
                    link_tag = cols[2].find('a')
                    link = link_tag['href'] if link_tag else ""
                    fund_type = cols[3].get_text(strip=True)
                    
                    funds.append({
                        "albo": albo,
                        "name": name,
                        "link": link,
                        "type": fund_type
                    })
        return funds
    except Exception as e:
        print(f"Error fetching funds: {e}")
        return []

def extract_costs_from_pdf(pdf_url):
    data = {"general_costs": [], "chart_image": None, "debug_log": []}
    debug_log = data["debug_log"]
    
    try:
        debug_log.append(f"Fetching PDF: {pdf_url}")
        res = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, verify=False)
        
        with pdfplumber.open(io.BytesIO(res.content)) as pdf:
            debug_log.append(f"Total Pages: {len(pdf.pages)}")
            
            # STRATEGY: ABSOLUTE LAST VISUAL CHART
            # User Feedback: "Il ragionamento vale per tutto... E' l'ultimo grafico che trovi in ogni scheda costi"
            # Logic: Scan all pages for "Chart Candidates". Pick the LAST one.
            
            # STRATEGY: SCOPED LAST GRAPH
            # User Feedback: "E' l'ultimo grafico che trovi in ogni scheda costi"
            # Insight: Use "Absolute Last" but filter out irrelevant pages (like back covers).
            # Logic: 
            # 1. Identify "Relevant Pages" (contain "Onerosità", "ISC", "Grafico").
            # 2. From these (and their immediate successors), pick the Last Visual Candidate.
            
            candidates = []
            
            # First, scan for relevancy to define a "Search Window"
            # We don't want to scan the back cover of a 50 page document.
            last_relevant_page_idx = -1
            for i, page in enumerate(pdf.pages):
                text = (page.extract_text() or "").lower()
                if "onerosita" in text or "isc" in text or "grafico" in text:
                    last_relevant_page_idx = i
            
            # If we found relevant pages, extend window by 1 (charts often follow title)
            search_end_idx = len(pdf.pages)
            if last_relevant_page_idx != -1:
                search_end_idx = min(len(pdf.pages), last_relevant_page_idx + 2)
            
            debug_log.append(f"Search Window: Pages 0 to {search_end_idx}")

            for i in range(search_end_idx):
                page = pdf.pages[i]
                if i == 0: continue # Skip cover
                
                # Check 1: Large Images
                last_img_on_page = None
                img_y = 0
                for img in page.images:
                    try:
                        w = float(img['width'])
                        h = float(img['height'])
                        # Metric: Chart-like aspect ratio? 
                        # Or just size.
                        if w > 200 and h > 100:
                            img_y = float(img['top'])
                            last_img_on_page = img
                    except: pass
                
                if last_img_on_page:
                    candidates.append({
                        "type": "image",
                        "page_idx": i,
                        "obj": last_img_on_page,
                        "y": img_y,
                        "desc": f"Large Image (Page {i+1})"
                    })
                    continue # Prefer image
                    
                # Check 2: Vectors (Rects + Keyword)
                if len(page.rects) > 30:
                     text = (page.extract_text() or "").lower()
                     if "isc" in text or "onerosita" in text:
                        candidates.append({
                            "type": "vector",
                            "page_idx": i,
                            "obj": None,
                            "y": 100,
                            "desc": f"Vector Chart (Page {i+1})"
                        })

            target = None
            if candidates:
                target = candidates[-1]
                debug_log.append(f"Selected Target: {target['desc']}")
            else:
                 debug_log.append("No candidates in window. Fallback to wide search.")
                 # ... Fallback existing logic ...
            
            if target:
                chart_page = pdf.pages[target['page_idx']]
                
                # CROP LOGIC
                crop_top = 0
                crop_bottom = chart_page.height
                
                if target['type'] == 'image':
                    img = target['obj']
                    # Use Image Vertical Bounds + Margin
                    img_top = float(img['top'])
                    img_height = float(img['height'])
                    if 'bottom' in img:
                        img_bottom = float(img['bottom'])
                    else:
                        img_bottom = img_top + img_height
                        
                    crop_top = max(0, img_top - 30)
                    crop_bottom = min(float(chart_page.height), img_bottom + 80)
                    
                elif target['type'] == 'vector' or target['type'] == 'text':
                    # Find Text Anchor
                    words = chart_page.extract_words()
                    anchor_y = 100
                    found = False
                    # Look for "Onerosità" title
                    for w in words:
                        if "onerosita" in w['text'].lower() and float(w['top']) < 400:
                            anchor_y = float(w['top'])
                            found = True
                            break
                    
                    if not found and target['type'] == 'text': 
                         # Just top half
                         pass
                    
                    crop_top = max(0, anchor_y - 20)
                    crop_bottom = min(float(chart_page.height), crop_top + 550)

                # DEBUG SAFETY: Ensure width is valid (full width)
                # Some PDFs have negative margin boxes?
                
                final_box = (0, crop_top, chart_page.width, crop_bottom)
                debug_log.append(f"Cropping Page {target['page_idx']+1}: {final_box}")
                
                cropped = chart_page.crop(final_box)
                im = cropped.to_image(resolution=200)
                
                # Save
                url_hash = hashlib.md5(pdf_url.encode()).hexdigest()
                filename = f"chart_{url_hash}.png"
                filepath = os.path.join("static", filename)
                im.save(filepath, format="PNG")
                
                data["chart_image"] = f"/{filename}"

    except Exception as e:
        print(f"Error extracting PDF: {e}")
        debug_log.append(f"Error: {str(e)}")

    return data

def get_fund_returns(albo, name):
    return []
