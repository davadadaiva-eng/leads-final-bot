import os, requests, time
from dotenv import load_dotenv
load_dotenv()
# THE FIX: This line now looks for your Secret first!
YELP_API_KEY = os.getenv("YELP_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
# If TARGET_LOCATIONS secret exists, use it. Otherwise, use these defaults.
raw_locations = os.getenv("TARGET_LOCATIONS", "Paris France, Miami FL, New York NY")
LOCATIONS = [l.strip() for l in raw_locations.split(",")]
# Added French categories here too!
CATEGORIES = ["landscaping", "hvac", "plumbing", "roofing", "paysagiste", "climatisation", "plombier", "couvreur"]
PROCESSED_LEADS_FILE = "sent_leads.txt"
def send_to_discord(biz):
    payload = {
        "embeds": [{
            "title": f"🚨 GOLDEN LEAD: {biz['name']} (NO WEBSITE)",
            "url": biz['url'],
            "color": 15158332,
            "fields": [
                {"name": "Phone", "value": biz.get('display_phone', 'N/A'), "inline": True},
                {"name": "Location", "value": ", ".join(biz['location']['display_address']), "inline": False},
                {"name": "Rating", "value": f"⭐ {biz.get('rating')} ({biz.get('review_count')} reviews)", "inline": True}
            ],
            "footer": {"text": "Verified: No website found."}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)
def run():
    processed = set()
    if os.path.exists(PROCESSED_LEADS_FILE):
        with open(PROCESSED_LEADS_FILE, "r") as f: processed = set(line.strip() for line in f)
    for loc in LOCATIONS:
        for cat in CATEGORIES:
            print(f"🔎 Searching {cat} in {loc}...")
            headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
            params = {"term": cat, "location": loc, "limit": 20}
            
            try:
                res = requests.get("https://api.yelp.com/v3/businesses/search", headers=headers, params=params)
                businesses = res.json().get("businesses", [])
                
                for b in businesses:
                    if b['id'] in processed: continue
                    
                    # We check for website here
                    details = requests.get(f"https://api.yelp.com/v3/businesses/{b['id']}", headers=headers).json()
                    website = details.get('website')
                    
                    if not website or website == "" or "yelp.com" in website:
                        send_to_discord(details)
                        with open(PROCESSED_LEADS_FILE, "a") as f: f.write(f"{b['id']}\n")
                        processed.add(b['id'])
                        time.sleep(1)
            except Exception as e:
                print(f"Error in {loc}: {e}")
if __name__ == "__main__": run()
