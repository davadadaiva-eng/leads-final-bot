import os, requests, time
from dotenv import load_dotenv
load_dotenv()
YELP_API_KEY = os.getenv("YELP_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
# Get locations from Secrets, or use these 3 defaults
LOCATIONS = [l.strip() for l in os.getenv("TARGET_LOCATIONS", "Austin TX, Miami FL, Dallas TX").split(",")]
CATEGORIES = ["landscaping", "hvac", "plumbing", "roofing"]
PROCESSED_LEADS_FILE = "sent_leads.txt"
def send_to_discord(biz):
    payload = {
        "embeds": [{
            "title": f"🚨 NEW LEAD: {biz['name']} (NO WEBSITE)",
            "url": biz['url'],
            "color": 15158332, # Red for urgency
            "fields": [
                {"name": "Phone", "value": biz.get('display_phone', 'N/A'), "inline": True},
                {"name": "Location", "value": ", ".join(biz['location']['display_address']), "inline": False},
                {"name": "Rating", "value": f"⭐ {biz.get('rating')} ({biz.get('review_count')} reviews)", "inline": True}
            ],
            "footer": {"text": "Verified: Business has no website listed on Yelp."}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)
def run():
    processed = set()
    if os.path.exists(PROCESSED_LEADS_FILE):
        with open(PROCESSED_LEADS_FILE, "r") as f: processed = set(line.strip() for line in f)
    for loc in LOCATIONS:
        for cat in CATEGORIES:
            print(f"Searching {cat} in {loc}...")
            headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
            params = {"term": cat, "location": loc, "limit": 20} # Looking at top 20
            
            try:
                res = requests.get("https://api.yelp.com/v3/businesses/search", headers=headers, params=params)
                businesses = res.json().get("businesses", [])
                
                for b in businesses:
                    if b['id'] in processed: continue
                    
                    # STRICT FILTER: Check if the 'website' field is missing or empty
                    # We have to get full details for each business to be 100% sure
                    details = requests.get(f"https://api.yelp.com/v3/businesses/{b['id']}", headers=headers).json()
                    
                    website = details.get('website')
                    
                    if not website or website == "" or "yelp.com" in website:
                        print(f"Found Golden Lead: {b['name']}")
                        send_to_discord(details)
                        with open(PROCESSED_LEADS_FILE, "a") as f: f.write(f"{b['id']}\n")
                        processed.add(b['id'])
                        time.sleep(1) # Safety delay
            except Exception as e:
                print(f"Error: {e}")
if __name__ == "__main__": run()
