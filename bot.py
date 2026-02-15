import discord
from discord.ext import tasks, commands
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json
import os
import asyncio
import time
from datetime import datetime

# --- CONFIGURATION LOADING ---
if not os.path.exists('config.json'):
    print("❌ Error: config.json not found! Please create it.")
    exit()

with open('config.json', 'r') as f:
    config = json.load(f)

TOKEN = config['token']
CHANNEL_ID = int(config['channel_id'])
KEYWORDS = [k.lower() for k in config['keywords']]
DATA_FILE = 'data/seen_bundles.json'

# --- SETUP DISCORD BOT ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# --- PERSISTENCE FUNCTIONS ---
def load_seen_bundles():
    if not os.path.exists('data'):
        os.makedirs('data')
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return set(json.load(f))
        except json.JSONDecodeError:
            return set()
    return set()

def save_seen_bundles(seen_set):
    with open(DATA_FILE, 'w') as f:
        json.dump(list(seen_set), f)

# --- MAIN LOGIC ---
class HumbleScraper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.seen_bundles = load_seen_bundles()
        self.check_deals.start()

    def cog_unload(self):
        self.check_deals.cancel()

    @tasks.loop(hours=6)
    async def check_deals(self):
        print(f"[{datetime.now()}] 🔍 Launching Chrome to check Humble Bundle...")
        
        # --- SELENIUM SETUP ---
        chrome_options = Options()
        chrome_options.add_argument("--headless") # Run in background (invisible)
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # This keeps the browser log clean
        chrome_options.add_argument("--log-level=3") 

        try:
            # Auto-install the correct chromedriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Go to the bundles page
            url = "https://www.humblebundle.com/bundles"
            driver.get(url)
            
            # WAIT for JavaScript to load the deals (Crucial step!)
            time.sleep(5) 
            
            # Get the fully rendered HTML
            page_source = driver.page_source
            driver.quit() # Close Chrome
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, "html.parser")
            
            print(f"✅ Page Loaded. found {len(soup.find_all('a', href=True))} links.")

            found_new = False
            
            # Look for bundle tiles
            # Humble bundle tiles are usually wrapped in anchors
            for link_tag in soup.find_all('a', href=True):
                href = link_tag['href']
                
                # Filter strictly for bundle pages
                if '/bundles/' not in href and '/software/' not in href and '/books/' not in href:
                    continue
                
                # Ignore navigation links
                if href in ["/bundles", "/books", "/software", "/games"]:
                    continue

                # ID and Name Extraction
                machine_name = href.split('/')[-1]
                
                # Try to get text, fallback to aria-label
                name = link_tag.get_text(strip=True)
                if not name:
                    name = link_tag.get('aria-label') or machine_name

                # Filter out garbage short names (sometimes "Image" or "Detail")
                if len(name) < 3: 
                    continue

                full_link = f"https://www.humblebundle.com{href}"
                
                # Check 1: Have we seen this ID?
                if machine_name in self.seen_bundles:
                    continue

                # Check 2: Keywords
                search_text = (name + " " + machine_name).lower()
                
                if any(keyword in search_text for keyword in KEYWORDS):
                    print(f"🚨 MATCH FOUND: {name}")
                    await self.post_deal(name, full_link, machine_name)
                    self.seen_bundles.add(machine_name)
                    found_new = True

            if found_new:
                save_seen_bundles(self.seen_bundles)
                print("💾 Saved new deals.")
            else:
                print("💤 No new relevant deals found.")

        except Exception as e:
            print(f"❌ Error during scrape: {e}")
            # Ensure driver closes if it crashes
            try:
                driver.quit()
            except:
                pass

    async def post_deal(self, name, link, machine_name):
        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel:
            print(f"❌ Error: Could not find channel {CHANNEL_ID}")
            return

    
        # Discord limit is 256. We subtract some space for our "New CS Bundle" prefix.
        safe_name = name
        if len(safe_name) > 200:
            safe_name = safe_name[:200] + "..."

        embed = discord.Embed(
            title=f"📚 New CS Bundle: {safe_name}",
            url=link,
            description="A new bundle matching your keywords was found!",
            color=0x00FF00
        )
        embed.set_thumbnail(url="https://humblebundle.com/favicon.ico")
        embed.set_footer(text=f"ID: {machine_name}")

        await channel.send(embed=embed)
        print(f"🚀 Sent alert for: {safe_name}")

# --- RUN BOT ---
@bot.event
async def on_ready():
    print(f'🤖 Logged in as {bot.user}')
    await bot.add_cog(HumbleScraper(bot))

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("❌ Invalid Token.")