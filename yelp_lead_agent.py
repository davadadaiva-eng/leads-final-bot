import os
import requests
import time
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv()

# Configuration
YELP_API_KEY = os.getenv("YELP_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
LOCATIONS = [l.strip() for l in os.getenv("TARGET_LOCATIONS", "Austin TX").split(",")]
CATEGORIES = [c.strip() for c in os.getenv("TARGET_CATEGORIES", "landscaping, hvac, plumbing, roofing").split(",")]
PROCESSED_LEADS_FILE = os.path.join(os.path.dirname(__file__), "sent_leads.txt")

YELP_BASE_URL = "https://api.yelp.com/v3/businesses"

def load_processed_leads():
    """Loads IDs of businesses already sent to Discord."""
    if os.path.exists(PROCESSED_LEADS_FILE):
        with open(PROCESSED_LEADS_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_processed_lead(biz_id):
    """Saves a business ID to the processed list."""
    with open(PROCESSED_LEADS_FILE, "a") as f:
        f.write(f"{biz_id}\n")

def get_business_details(business_id):
    """Fetches full details including the actual website URL."""
    url = f"{YELP_BASE_URL}/{business_id}"
    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"  [Error] fetching details for {business_id}: {e}")
    return None

def check_website_quality(url):
    """
    Analyzes a website to see if it's 'bad' or outdated.
    Returns (is_bad, reason)
    """
    if not url:
        return True, "No website found"
    
    try:
        # Use a real browser-like User-Agent to avoid blocks
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        
        # 1. Check if the site is even reachable
        if response.status_code >= 400:
            return True, f"Site returns error {response.status_code}"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        reasons = []
        
        # 2. Check for Mobile Friendly (Viewport tag)
        if not soup.find("meta", attrs={"name": "viewport"}):
            reasons.append("Not mobile-friendly (missing viewport tag)")
            
        # 3. Check for Security (HTTPS)
        if not url.startswith("https"):
            reasons.append("Not secure (HTTP)")
            
        # 4. Check for 'Under Construction' or placeholders
        title = soup.title.string.lower() if soup.title else ""
        if "under construction" in title or "coming soon" in title:
            reasons.append("Site is under construction/placeholder")

        # 5. Check for thin content (very low text amount)
        if len(response.text) < 2000:
            reasons.append("Very thin content (potential placeholder)")

        if reasons:
            return True, " | ".join(reasons)
        
        return False, "Site looks okay"

    except Exception as e:
        return True, f"Could not connect: {str(e)[:50]}"

def send_to_discord(business, website_status, reason):
    """Sends the lead to Discord with its 'Bad Website' report."""
    color = 15158332 if website_status else 3066993 # Red if bad, Green if good (though we mostly send bad)
    
    website_url = business.get('attributes', {}).get('business_website', business.get('website', 'None'))
    
    fields = [
        {"name": "Category", "value": business.get('categories', [{}])[0].get('title', 'N/A'), "inline": True},
        {"name": "Phone", "value": business.get('display_phone', 'N/A'), "inline": True},
        {"name": "Rating", "value": f"Rating: {business.get('rating')} ({business.get('review_count')} reviews)", "inline": True},
        {"name": "Address", "value": ", ".join(business['location']['display_address'])},
        {"name": "Website Status", "value": f"FLAG: **{reason}**"},
    ]
    
    if website_url and website_url != 'None':
        fields.append({"name": "Current Website", "value": website_url})

    embed = {
        "title": f"Lead: {business['name']}",
        "url": business['url'], # Link to Yelp page
        "color": color,
        "fields": fields,
        "footer": {"text": "Yelp Lead Agent + Website Auditor"}
    }
    
    payload = {"embeds": [embed]}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"  [Error] Discord: {e}")

def run_agent():
    print("Starting Lead Agent with Website Auditor...")
    processed_leads = load_processed_leads()
    print(f"Loaded {len(processed_leads)} previously sent leads.")
    
    new_leads_found = 0
    
    for loc in LOCATIONS:
        for cat in CATEGORIES:
            print(f"Searching {cat} in {loc}...")
            url = "https://api.yelp.com/v3/businesses/search"
            headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
            params = {"term": cat, "location": loc, "limit": 20}
            
            try:
                response = requests.get(url, headers=headers, params=params)
                businesses = response.json().get("businesses", [])
                
                for b in businesses:
                    biz_id = b['id']
                    
                    # NEVER REPEAT: Skip if already sent
                    if biz_id in processed_leads:
                        continue
                    
                    print(f"  Checking {b['name']}...")
                    
                    # Get full details to find the website
                    details = get_business_details(biz_id)
                    if not details: continue
                    
                    website = details.get('website')
                    is_bad, reason = check_website_quality(website)
                    
                    if is_bad:
                        print(f"  Found New Lead: {b['name']} ({reason})")
                        send_to_discord(details, True, reason)
                        save_processed_lead(biz_id)
                        processed_leads.add(biz_id)
                        new_leads_found += 1
                        time.sleep(2) # Prevent rate limiting
                        
            except Exception as e:
                print(f"[Error] in loop: {e}")
    
    print(f"Done! Sent {new_leads_found} new leads today.")

if __name__ == "__main__":
    run_agent()
