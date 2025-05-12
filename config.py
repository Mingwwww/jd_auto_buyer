import os
import random
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# List of realistic user agents to rotate
DESKTOP_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]


class JDConfig(BaseModel):
    """Configuration for JD Auto Buyer"""
    # JD account credentials
    username: str = os.getenv('JD_USERNAME', '')
    password: str = os.getenv('JD_PASSWORD', '')
    
    # Browser settings
    headless: bool = os.getenv('HEADLESS', 'False').lower() == 'true'
    slow_mo: int = int(os.getenv('SLOW_MO', '50'))
    user_agent: str = os.getenv('USER_AGENT', random.choice(DESKTOP_USER_AGENTS))
    
    # Anti-detection settings
    randomize_mouse_movements: bool = True
    humanize_navigation: bool = True
    add_random_delays: bool = True
    enable_stealth_mode: bool = True
    
    # Delay ranges (min, max) in seconds for random waits
    delay_ranges: Dict[str, List[float]] = {
        "navigation": [1.0, 4.0],       # After page navigation
        "interaction": [0.3, 1.2],      # Between user interactions (clicks, typing)
        "scrolling": [0.2, 0.9],        # Between scroll events
        "retry": [1.5, 4.0]             # Between retry attempts
    }
    
    # Shopping settings
    search_keywords: List[str] = []
    max_price: Optional[float] = None
    
    # URLs
    login_url: str = "https://passport.jd.com/login.aspx"
    homepage_url: str = "https://www.jd.com/"
    cart_url: str = "https://cart.jd.com/cart.action"
    
    # Alternative URLs to try if main ones fail
    alternative_urls: Dict[str, List[str]] = {
        "homepage": [
            "https://www.jd.com",
            "https://www.jd.com/index.html",
            "https://jd.com"
        ],
        "cart": [
            "https://cart.jd.com/cart.action",
            "https://cart.jd.com/cart_index",
            "https://cart.jd.com/addToCart.html",
            "https://cart.jd.com/cart/cart.action"
        ],
        "mobile_cart": [
            "https://p.m.jd.com/cart/cart.action",
            "https://cart-m.jd.com",
            "https://wq.jd.com/cart/view",
            "https://wqs.jd.com/my/cart.shtml"
        ]
    }
    
    # Backup domains if regular domains are blocked
    backup_domains: bool = True
    
    # File paths
    cookies_path: str = str(Path(__file__).parent / "cookies.json")
    screenshots_dir: str = str(Path(__file__).parent / "screenshots")
    
    # Retry settings
    max_retries: int = 5  # Increased from 3
    retry_delay: int = 2  # seconds
    wait_after_navigation: int = 2  # seconds
    
    # Timeouts (in milliseconds)
    navigation_timeout: int = 30000
    action_timeout: int = 15000
    
    # When True, will attempt to use mobile version of site if desktop fails
    try_mobile_fallback: bool = True
    
    def get_random_delay(self, delay_type: str) -> float:
        """Get a random delay within the specified range for more human-like behavior"""
        delay_range = self.delay_ranges.get(delay_type, [0.5, 1.5])
        return random.uniform(delay_range[0], delay_range[1])
    
    def get_random_user_agent(self, mobile: bool = False) -> str:
        """Get a random user agent, optionally for mobile devices"""
        if mobile:
            mobile_agents = [
                "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (iPad; CPU OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Mobile Safari/537.36",
                "Mozilla/5.0 (Linux; Android 12; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Mobile Safari/537.36"
            ]
            return random.choice(mobile_agents)
        else:
            return random.choice(DESKTOP_USER_AGENTS)


# Create default config instance
config = JDConfig()

# Initialize search keywords with food items examples
config.search_keywords = os.getenv('SEARCH_KEYWORDS', '水果,零食,饮料').split(',')
if os.getenv('MAX_PRICE'):
    config.max_price = float(os.getenv('MAX_PRICE'))
