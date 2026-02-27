#!/usr/bin/env python3
"""
WhatsApp Login - First-time QR Code Scanner

Opens a VISIBLE browser so you can scan the QR code with your phone.
After login, session is saved for future watcher runs.

Usage:
    python whatsapp_login.py
"""

import logging
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT = Path(__file__).parent.resolve()
SESSION_PATH = VAULT_ROOT / "session" / "whatsapp"
LOGS_DIR = VAULT_ROOT / "Logs"

WHATSAPP_URL = "https://web.whatsapp.com"

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("whatsapp_login")

# ─────────────────────────────────────────────────────────────────────────────
# Login Function
# ─────────────────────────────────────────────────────────────────────────────


def login_to_whatsapp():
    """Open visible browser for QR code scanning."""
    
    print("")
    print("=" * 60)
    print("  📱 WhatsApp Login - QR Code Scanner")
    print("=" * 60)
    print("")
    print("📋 Instructions:")
    print("   1. A browser window will open with WhatsApp Web")
    print("   2. Open WhatsApp on your phone")
    print("   3. Go to: Settings → Linked Devices")
    print("   4. Tap 'Link a Device'")
    print("   5. Scan the QR code shown in the browser")
    print("   6. Wait for 'Login successful' message")
    print("")
    print("⏱️  You have 2 minutes to scan the QR code")
    print("")
    
    # Ensure session directory exists
    SESSION_PATH.mkdir(parents=True, exist_ok=True)
    
    try:
        with sync_playwright() as p:
            # Launch VISIBLE browser with persistent context (saves session)
            print("🌐 Opening browser...")
            print(f"📁 Session will be saved to: {SESSION_PATH}")
            print("")
            
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(SESSION_PATH),
                headless=False,  # IMPORTANT: Visible browser!
                viewport={"width": 1280, "height": 800},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            
            page = browser.pages[0]
            
            print("📲 Navigating to WhatsApp Web...")
            page.goto(WHATSAPP_URL, wait_until="networkidle", timeout=60000)
            
            print("")
            print("⏳ Waiting for QR code scan...")
            print("   (Browser window should be visible on your screen)")
            print("")
            
            # Wait for login (check for chat list element)
            max_wait = 120  # 2 minutes
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                try:
                    # Check if logged in (chat list appears)
                    if page.query_selector("div[role='heading'], div[data-testid='cell-frame-container']"):
                        print("")
                        print("✅ Login successful!")
                        print("")
                        print("📁 Session saved to:", SESSION_PATH)
                        print("")
                        print("Next time you run whatsapp_watcher.py, no QR scan needed!")
                        print("")
                        
                        # Wait a moment for session to fully save
                        time.sleep(3)
                        break
                except Exception:
                    pass
                
                time.sleep(2)
            else:
                print("")
                print("⚠️  Login timeout - QR code expired")
                print("")
                print("Please run the script again to get a new QR code.")
                print("")
            
            # Close browser
            print("🔒 Closing browser...")
            browser.close()
            
    except Exception as e:
        print("")
        print(f"❌ Error: {e}")
        print("")
        print("Troubleshooting:")
        print("   1. Run: playwright install chromium")
        print("   2. Try running as Administrator")
        print("   3. Make sure Python has access to create folders")
        print("")
        sys.exit(1)
    
    print("=" * 60)
    print("  Login Complete!")
    print("=" * 60)
    print("")
    
    # Test the watcher
    print("🧪 Want to test the WhatsApp Watcher now?")
    print("")
    print("   1. Send yourself a WhatsApp message with keyword:")
    print("      'URGENT: Test message for payment'")
    print("")
    print("   2. Run the watcher:")
    print("      python Watchers/whatsapp_watcher.py")
    print("")
    print("   3. Check Needs_Action folder for new task file")
    print("")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    login_to_whatsapp()
