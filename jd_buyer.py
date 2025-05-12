#!/usr/bin/env python3
import asyncio
import json
import os
import random
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError
from loguru import logger

from config import config


class JDAutoBuyer:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Create screenshots directory if it doesn't exist
        Path(config.screenshots_dir).mkdir(exist_ok=True)

    async def setup(self):
        """Initialize browser with enhanced anti-bot configurations"""
        logger.info("Setting up browser with anti-bot evasion...")
        playwright = await async_playwright().start()
        
        # Enhanced browser arguments to avoid detection
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-web-security',
            '--disable-site-isolation-trials',
            '--no-sandbox',
            '--mute-audio',  # Prevent AudioContext errors
            '--disable-extensions',
            '--autoplay-policy=no-user-gesture-required',  # Allow audio autoplay without user gesture
            f'--window-size=1280,{random.randint(800, 900)}',  # Randomize window size slightly
        ]
        
        # Create a more human-like browser instance
        self.browser = await playwright.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo,
            args=browser_args
        )
        
        # Create context with enhanced privacy settings and fingerprinting evasion
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': random.randint(800, 900)},
            user_agent=config.user_agent,
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            has_touch=random.choice([True, False]),  # Randomize touch capability
            device_scale_factor=random.choice([1, 2]),  # Randomize device scale factor
            is_mobile=False,
            color_scheme='light',
            permissions=["geolocation", "notifications", "microphone", "camera"]  # Pre-grant permissions
        )
        
        # Modify JavaScript environment to prevent detection with specific focus on fixing AudioContext issues
        await self.context.add_init_script("""
        () => {
            // Override properties that automation detection checks for
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' || 
                parameters.name === 'clipboard-read' || 
                parameters.name === 'clipboard-write' ?
                Promise.resolve({ state: 'granted', onchange: null }) :
                originalQuery(parameters)
            );
            
            // Specific fix for the AudioContext error mentioned in the error message
            const simulateUserGesture = () => {
                // Create and dispatch a user gesture event
                const clickEvent = new MouseEvent('click', {
                    view: window,
                    bubbles: true,
                    cancelable: true,
                    clientX: Math.floor(Math.random() * window.innerWidth),
                    clientY: Math.floor(Math.random() * window.innerHeight)
                });
                document.body && document.body.dispatchEvent(clickEvent);
            };
            
            // Replace AudioContext with a version that auto-resumes
            const OriginalAudioContext = window.AudioContext || window.webkitAudioContext;
            
            if (OriginalAudioContext) {
                class PatchedAudioContext extends OriginalAudioContext {
                    constructor(options) {
                        super(options);
                        // Auto-resume on creation
                        if (this.state === 'suspended') {
                            simulateUserGesture();
                            this.resume();
                        }
                    }
                    
                    // Override resume method to simulate user gesture
                    resume() {
                        simulateUserGesture();
                        return super.resume();
                    }
                }
                
                // Replace the original AudioContext
                window.AudioContext = PatchedAudioContext;
                window.webkitAudioContext = PatchedAudioContext;
                
                // Fix for the specific error in td.js
                if (typeof window.audioKey !== 'undefined') {
                    try {
                        simulateUserGesture();
                        // If audioKey is a function, override it
                        if (typeof window.audioKey === 'function') {
                            const originalAudioKey = window.audioKey;
                            window.audioKey = function(...args) {
                                simulateUserGesture();
                                return originalAudioKey.apply(this, args);
                            };
                        }
                    } catch (e) {
                        console.log('Error patching audioKey', e);
                    }
                }
            }
            
            // Patch any existing AudioContext instances
            document.addEventListener('DOMContentLoaded', () => {
                simulateUserGesture();
                setTimeout(simulateUserGesture, 1000);
                setTimeout(simulateUserGesture, 2000);
            });
            
            // Add language plugins that real browsers usually have
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en']
            });
            
            // Patch the JD specific detection mechanism
            // This directly addresses issues with JD's td.js
            if (typeof window.td !== 'undefined') {
                try {
                    const originalEval = window.eval;
                    window.eval = function(code) {
                        // Check if this is td.js related code
                        if (code && typeof code === 'string' && (code.includes('audioKey') || code.includes('td.js'))) {
                            simulateUserGesture();
                            // Add user gesture simulation before evaluating
                            code = 'try { document.body.dispatchEvent(new MouseEvent("click")); } catch(e) {} ' + code;
                        }
                        return originalEval(code);
                    };
                } catch (e) {
                    console.log('Error patching eval', e);
                }
            }
        }
        """)
        
        # Add an event listener to handle all potential AudioContext issues during navigation
        await self.context.add_init_script("""
        window.addEventListener('error', function(e) {
            // Check if error is related to AudioContext
            if (e && e.message && e.message.includes('AudioContext')) {
                // Try to simulate user gesture to unblock audio
                const event = new MouseEvent('click', {
                    'view': window,
                    'bubbles': true,
                    'cancelable': true
                });
                document.body.dispatchEvent(event);
                
                // Try to resume any existing audio contexts
                if (window.audioContexts) {
                    window.audioContexts.forEach(ctx => {
                        if (ctx && ctx.state === 'suspended') {
                            ctx.resume();
                        }
                    });
                }
            }
        }, true);
        """)
        
        self.page = await self.context.new_page()
        
        # Enable all permissions
        context_permissions = ["geolocation", "notifications", "microphone", "camera"]
        for permission in context_permissions:
            await self.context.grant_permissions([permission])
        
        # Set navigation timeout
        self.page.set_default_navigation_timeout(config.navigation_timeout)
        self.page.set_default_timeout(config.action_timeout)
        
        # Add human-like headers 
        await self.page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Pragma': 'no-cache',
            'DNT': '1'
        })
        
        # Listen for all console messages to debug
        self.page.on("console", lambda msg: logger.debug(f"Browser console: {msg.text}"))
        
        # Listen for page errors
        self.page.on("pageerror", lambda err: logger.error(f"Page error: {err}"))
        
        logger.info("Enhanced browser setup completed")

    async def close(self):
        """Close browser and clean up"""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")

    async def _handle_verification(self, timeout=60000) -> bool:
        """Handle various verification challenges that may appear"""
        try:
            logger.info("Checking for verification challenges...")
            
            # Check for slide verification
            slide_verification = await self.page.query_selector('.JDJRV-slide-bg')
            if slide_verification:
                logger.warning("Slide verification detected. Please complete it manually.")
                # Take screenshot of verification
                await self.page.screenshot(path=f"{config.screenshots_dir}/slide_verification.png")
                logger.info(f"Verification screenshot saved to {config.screenshots_dir}/slide_verification.png")
                
                # Wait for manual verification to complete
                await self.page.wait_for_selector('.nickname', timeout=timeout)
                logger.info("Verification completed!")
                return True
            
            # Check for SMS verification
            sms_verification = await self.page.query_selector('.mobile-code')
            if sms_verification:
                logger.warning("SMS verification detected. Please complete it manually.")
                # Take screenshot of verification
                await self.page.screenshot(path=f"{config.screenshots_dir}/sms_verification.png")
                logger.info(f"Verification screenshot saved to {config.screenshots_dir}/sms_verification.png")
                
                # Wait for manual verification to complete
                await self.page.wait_for_selector('.nickname', timeout=timeout)
                logger.info("Verification completed!")
                return True
                
            # Check for CAPTCHA
            captcha = await self.page.query_selector('.verify-img')
            if captcha:
                logger.warning("CAPTCHA verification detected. Please complete it manually.")
                # Take screenshot of verification
                await self.page.screenshot(path=f"{config.screenshots_dir}/captcha_verification.png")
                logger.info(f"Verification screenshot saved to {config.screenshots_dir}/captcha_verification.png")
                
                # Wait for manual verification to complete
                await self.page.wait_for_selector('.nickname', timeout=timeout)
                logger.info("Verification completed!")
                return True
                
            # Check for any other verification iframe
            verification_frame = await self.page.query_selector('iframe[src*="verify"]')
            if verification_frame:
                logger.warning("Verification iframe detected. Please complete it manually.")
                # Take screenshot of verification
                await self.page.screenshot(path=f"{config.screenshots_dir}/iframe_verification.png")
                logger.info(f"Verification screenshot saved to {config.screenshots_dir}/iframe_verification.png")
                
                # Wait for manual verification to complete or timeout
                await self.page.wait_for_selector('.nickname', timeout=timeout)
                logger.info("Verification completed!")
                return True
                
            # No verification needed
            return False
            
        except TimeoutError:
            logger.error("Verification timeout. User did not complete verification in time.")
            return False
        except Exception as e:
            logger.error(f"Error handling verification: {str(e)}")
            return False

    async def login(self) -> bool:
        """Login to JD.com via username/password or QR code or saved cookies"""
        if await self._load_cookies():
            logger.info("Successfully logged in with cookies")
            return True
        
        logger.info("No valid cookies found, attempting login...")
        
        try:
            await self.page.goto(config.login_url)
            
            # Try username/password login if credentials are available
            if config.username and config.password:
                logger.info("Attempting login with username and password")
                
                # Switch to account login if needed
                account_login_tab = await self.page.query_selector('//a[contains(text(), "账户登录")]')
                if account_login_tab:
                    await account_login_tab.click()
                
                # Enter username
                await self.page.fill('#loginname', config.username)
                
                # Enter password
                await self.page.fill('#nloginpwd', config.password)
                
                # Click login button
                login_button = await self.page.query_selector('.login-btn')
                if login_button:
                    await login_button.click()
                    
                    # Wait for login success or failure
                    try:
                        # Handle any verification challenges
                        if await self._handle_verification(timeout=60000):
                            # Verification successful, save cookies
                            await self._save_cookies()
                            return True
                            
                        # Check for login success
                        await self.page.wait_for_selector('.nickname', timeout=10000)
                        logger.info("Login successful with username/password!")
                        
                        # Save cookies
                        await self._save_cookies()
                        return True
                    except TimeoutError:
                        # Check for error message
                        error_msg = await self.page.query_selector('.msg-error')
                        if error_msg:
                            error_text = await error_msg.text_content()
                            logger.error(f"Login failed: {error_text}")
                        else:
                            logger.error("Login with username/password failed")
                        
                        # Fall back to QR code login
                        logger.info("Falling back to QR code login")
            else:
                logger.info("Username or password not provided, using QR code login")
            
            # Switch to QR code login
            qr_login_tab = await self.page.query_selector('//a[contains(text(), "扫码登录")]')
            if qr_login_tab:
                await qr_login_tab.click()
            
            # Take screenshot of QR code
            qr_code = await self.page.query_selector('.qrcode-img')
            if qr_code:
                qr_path = f"{config.screenshots_dir}/qr_code.png"
                await qr_code.screenshot(path=qr_path)
                logger.info(f"QR code saved to {qr_path}")
                logger.info("Please scan the QR code with your JD app to login")
            
            # Wait for login success
            await self.page.wait_for_selector('.nickname', timeout=120000)  # 2 minutes to scan
            logger.info("Login successful!")
            
            # Save cookies
            await self._save_cookies()
            return True
            
        except TimeoutError:
            logger.error("Login timeout. Please try again.")
            return False
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False

    async def _save_cookies(self):
        """Save cookies to file"""
        cookies = await self.context.cookies()
        with open(config.cookies_path, 'w') as f:
            json.dump(cookies, f)
        logger.info("Cookies saved")

    async def _load_cookies(self) -> bool:
        """Load cookies from file and verify if still valid"""
        try:
            if not os.path.exists(config.cookies_path):
                return False
                
            with open(config.cookies_path, 'r') as f:
                cookies = json.load(f)
                
            await self.context.add_cookies(cookies)
            
            # Verify cookies by visiting homepage
            await self.page.goto(config.homepage_url)
            
            # Check if logged in by looking for nickname
            nickname = await self.page.query_selector('.nickname')
            return nickname is not None
            
        except Exception as e:
            logger.error(f"Error loading cookies: {str(e)}")
            return False

    async def search_product(self, keyword: str) -> List[Dict]:
        """Search for products based on keyword"""
        logger.info(f"Searching for: {keyword}")
        
        try:
            # Ensure page is available
            if not await self._ensure_page_available():
                return []
                
            # Navigate to homepage
            await self.page.goto(config.homepage_url)
            
            # Input search keyword
            await self.page.fill('#key', keyword)
            await self.page.click('.button')
            
            # Wait for search results without timeout
            await self.page.wait_for_selector('.gl-item', timeout=0)  # timeout=0 means no timeout
            
            # Take screenshot
            await self.page.screenshot(path=f"{config.screenshots_dir}/search_results_{keyword.replace(' ', '_')}.png")
            
            # Extract product information
            products = await self.page.evaluate('''
                () => {
                    const items = Array.from(document.querySelectorAll('.gl-item'));
                    return items.map(item => {
                        const priceElement = item.querySelector('.p-price strong');
                        const nameElement = item.querySelector('.p-name em');
                        const linkElement = item.querySelector('.p-img a');
                        const commentElement = item.querySelector('.p-commit strong');
                        const shopElement = item.querySelector('.p-shop a');
                        
                        return {
                            id: item.getAttribute('data-sku') || '',
                            name: nameElement ? nameElement.innerText.trim() : '',
                            price: priceElement ? parseFloat(priceElement.innerText.replace('¥', '')) : 0,
                            link: linkElement ? linkElement.getAttribute('href') : '',
                            comments: commentElement ? commentElement.innerText.trim() : '0',
                            shop: shopElement ? shopElement.innerText.trim() : '',
                        };
                    });
                }
            ''')
            
            if config.max_price:
                products = [p for p in products if p['price'] <= config.max_price]
                
            logger.info(f"Found {len(products)} products matching {keyword}")
            return products
            
        except Exception as e:
            logger.error(f"Error searching for {keyword}: {str(e)}")
            return []

    def select_product_by_strategy(self, products: List[Dict], strategy: str = 'price_low') -> Optional[Dict]:
        """Select a product based on a strategy
        
        Strategies:
        - price_low: Select the product with the lowest price
        - price_high: Select the product with the highest price
        - first: Select the first product in the list (default JD ranking)
        - most_comments: Select the product with the most comments
        - random: Select a random product
        """
        if not products:
            return None
            
        if strategy == 'price_low':
            sorted_products = sorted(products, key=lambda p: p['price'])
            selected = sorted_products[0]
            logger.info(f"Selected lowest price product: {selected['name']} (¥{selected['price']})")
            
        elif strategy == 'price_high':
            sorted_products = sorted(products, key=lambda p: p['price'], reverse=True)
            selected = sorted_products[0]
            logger.info(f"Selected highest price product: {selected['name']} (¥{selected['price']})")
            
        elif strategy == 'most_comments':
            # Convert comment count to int for comparison
            for p in products:
                try:
                    p['comment_count'] = int(p['comments'].replace('+', '').replace('万', '0000'))
                except:
                    p['comment_count'] = 0
                    
            sorted_products = sorted(products, key=lambda p: p['comment_count'], reverse=True)
            selected = sorted_products[0]
            logger.info(f"Selected most reviewed product: {selected['name']} ({selected['comments']} reviews)")
            
        elif strategy == 'random':
            selected = random.choice(products)
            logger.info(f"Selected random product: {selected['name']} (¥{selected['price']})")
            
        else:  # default to first (JD's default ranking)
            selected = products[0]
            logger.info(f"Selected top ranked product: {selected['name']} (¥{selected['price']})")
            
        return selected

    async def add_to_cart(self, product: Dict) -> bool:
        """Add a product to shopping cart"""
        try:
            # Ensure page is available
            if not await self._ensure_page_available():
                return False
                
            product_url = product['link']
            if not product_url.startswith('http'):
                product_url = f"https:{product_url}"
                
            logger.info(f"Adding to cart: {product['name']} (¥{product['price']})")
            
            # Add anti-bot headers
            await self.page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'max-age=0',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1'
            })
            
            # Navigate to product page with retry logic
            for attempt in range(config.max_retries):
                try:
                    # Navigate to product page
                    await self.page.goto(product_url)
                    break  # Break the loop if navigation successful
                except Exception as e:
                    if attempt < config.max_retries - 1:
                        logger.warning(f"Navigation failed (attempt {attempt+1}/{config.max_retries}): {str(e)}")
                        await asyncio.sleep(config.retry_delay * (attempt + 1))
                    else:
                        logger.error(f"Failed to navigate to product page after {config.max_retries} attempts")
                        return False
            
            # Add random human-like delay
            await asyncio.sleep(random.uniform(1.0, 3.0))
            
            # Take screenshot
            await self.page.screenshot(path=f"{config.screenshots_dir}/product_{product['id']}.png")
            
            # Simulate some human-like activity
            viewport_height = await self.page.evaluate('window.innerHeight')
            page_height = await self.page.evaluate('document.body.scrollHeight')
            
            # Random scrolling
            scroll_positions = [random.randint(0, page_height) for _ in range(3)]
            for position in scroll_positions:
                await self.page.evaluate(f'window.scrollTo(0, {position})')
                await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Scroll back to add to cart area
            await self.page.evaluate('window.scrollTo(0, document.querySelector("#InitCartUrl") ? document.querySelector("#InitCartUrl").getBoundingClientRect().top - 100 : 0)')
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Click add to cart button with retry logic
            for attempt in range(config.max_retries):
                try:
                    # Find add to cart button
                    add_to_cart_btn = await self.page.query_selector('#InitCartUrl')
                    if not add_to_cart_btn:
                        add_to_cart_btn = await self.page.query_selector('.btn-addtocart')
                    
                    if not add_to_cart_btn:
                        # Try the second type of add-to-cart button
                        add_to_cart_btn = await self.page.query_selector('.btn-add')
                    
                    if not add_to_cart_btn:
                        # Try to find by text content
                        add_to_cart_btn = await self.page.query_selector("//a[contains(text(), '加入购物车')]")
                    
                    if not add_to_cart_btn:
                        logger.error("Add to cart button not found")
                        return False
                        
                    # Click the button
                    await add_to_cart_btn.click()
                    
                    # Wait for success dialog or success indication
                    success = False
                    try:
                        # Check for dialog
                        await self.page.wait_for_selector('.dialog-wrap', timeout=5000)
                        success = True
                    except TimeoutError:
                        # If no dialog, check if added to cart message appears
                        try:
                            added_msg = await self.page.wait_for_selector("//div[contains(text(), '已成功加入购物车')]", timeout=2000)
                            if added_msg:
                                success = True
                        except TimeoutError:
                            # If still no success, maybe it's already added (some items skip the confirmation)
                            if attempt == config.max_retries - 1:
                                logger.info("No confirmation dialog, assuming product was added")
                                success = True
                    
                    if success:
                        logger.info("Product added to cart successfully")
                        return True
                    
                    if attempt < config.max_retries - 1:
                        logger.warning(f"Add to cart may have failed (attempt {attempt+1}/{config.max_retries}), retrying...")
                        await asyncio.sleep(config.retry_delay * (attempt + 1))
                    else:
                        logger.warning("No confirmation after adding to cart, checking cart directly...")
                        # Try navigating to cart to verify
                        if await self.navigate_to_cart():
                            logger.info("Successfully navigated to cart, assuming product was added")
                            return True
                
                except Exception as e:
                    if attempt < config.max_retries - 1:
                        logger.warning(f"Error adding to cart (attempt {attempt+1}/{config.max_retries}): {str(e)}")
                        await asyncio.sleep(config.retry_delay * (attempt + 1))
                    else:
                        logger.error(f"Failed to add to cart after {config.max_retries} attempts: {str(e)}")
                        return False
            
            return False  # If we reached here, all attempts failed
                
        except Exception as e:
            logger.error(f"Error adding to cart: {str(e)}")
            return False

    async def _ensure_page_available(self) -> bool:
        """Ensure that page and context are available, recreate them if necessary"""
        try:
            if not self.page or self.page.is_closed():
                logger.warning("Page was closed, creating a new page")
                if not self.context or self.context.is_closed():
                    logger.warning("Context was closed, setting up browser again")
                    await self.setup()
                    if not await self.login():
                        logger.error("Failed to login after reopening browser")
                        return False
                else:
                    self.page = await self.context.new_page()
                    self.page.set_default_navigation_timeout(config.navigation_timeout)
                    self.page.set_default_timeout(config.action_timeout)
            return True
        except Exception as e:
            logger.error(f"Error ensuring page availability: {str(e)}")
            return False

    async def navigate_to_cart(self) -> bool:
        """Navigate to the shopping cart page with enhanced anti-detection"""
        try:
            logger.info("Navigating to shopping cart with anti-detection measures...")
            
            # Ensure page is available
            if not await self._ensure_page_available():
                return False
            
            # First go to homepage to establish session using a better approach
            for attempt in range(3):
                try:
                    # Add random referrer sometimes
                    if random.choice([True, False]):
                        await self.page.set_extra_http_headers({
                            'Referer': random.choice([
                                'https://www.baidu.com/s?wd=京东',
                                'https://www.sogou.com/web?query=京东商城',
                                'https://www.google.com/search?q=jd.com'
                            ])
                        })
                    
                    # Navigate with retries for 403 errors
                    response = await self.page.goto(config.homepage_url, wait_until="domcontentloaded")
                    if response.status == 403:
                        logger.warning(f"Got 403 on attempt {attempt+1}, retrying with different approach...")
                        await asyncio.sleep(random.uniform(3.0, 5.0))
                        # Clear cookies and try again with different settings
                        if attempt == 1:
                            await self.context.clear_cookies()
                            # Load cookies again
                            await self._load_cookies()
                        continue
                    break
                except Exception as e:
                    logger.warning(f"Navigation error on attempt {attempt+1}: {str(e)}")
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    if attempt == 2:
                        # Last attempt, try with a fresh context
                        await self.context.close()
                        self.context = await self.browser.new_context(
                            viewport={'width': 1280, 'height': random.randint(800, 900)},
                            user_agent=config.user_agent
                        )
                        await self._load_cookies()
                        self.page = await self.context.new_page()
            
            await asyncio.sleep(config.wait_after_navigation)
            
            # Simulate more realistic human behavior to avoid detection
            await self._perform_human_like_interaction()
            
            # Check if we need to handle verification
            if await self._handle_verification():
                logger.info("Verification handled successfully")
                await self._save_cookies()  # Save updated cookies
            
            # Try to get to cart with our enhanced methods
            cart_access_methods = [
                self._try_direct_cart_access,
                self._try_homepage_cart_link,
                self._try_minicart_access,
                self._try_alternate_cart_url,
                self._try_mobile_cart_access  # New mobile cart access method
            ]
            
            # Try each method until one works, with retry logic
            for method_index, method in enumerate(cart_access_methods):
                # Add randomized delay between attempts (more human-like)
                await asyncio.sleep(random.uniform(1.5, 3.0))
                
                logger.info(f"Trying cart access method {method_index + 1}/{len(cart_access_methods)}")
                
                # Try each method up to 2 times
                for retry in range(2):
                    if await method():
                        logger.info(f"Cart access method {method_index + 1} succeeded")
                        return True
                    
                    if retry < 1:
                        logger.info(f"Retrying method {method_index + 1}")
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                
                # If method failed, go back to homepage and try next method
                if method_index < len(cart_access_methods) - 1:
                    logger.info("Returning to homepage before trying next method")
                    try:
                        await self.page.goto(config.homepage_url)
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        await self._perform_human_like_interaction()
                    except Exception as e:
                        logger.warning(f"Error returning to homepage: {str(e)}")
            
            # If all methods fail
            logger.error("All cart access methods failed")
            return False
                
        except Exception as e:
            logger.error(f"Error navigating to cart: {str(e)}")
            return False

    async def _perform_human_like_interaction(self):
        """Perform realistic human-like interactions to avoid bot detection"""
        try:
            # Randomized mouse movements
            for _ in range(random.randint(3, 6)):
                x = random.randint(100, 1100)
                y = random.randint(100, 700)
                await self.page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.5))
            
            # Random scrolling patterns
            scroll_positions = [
                random.randint(200, 500),
                random.randint(500, 800),
                random.randint(800, 1200),
                random.randint(500, 900),
                random.randint(200, 400)
            ]
            
            for position in scroll_positions:
                await self.page.evaluate(f'window.scrollTo(0, {position})')
                await asyncio.sleep(random.uniform(0.3, 1.2))
            
            # Sometimes click on a random non-link element (like whitespace)
            if random.random() < 0.3:
                await self.page.mouse.click(
                    random.randint(200, 800),
                    random.randint(200, 600)
                )
            
            # Quick hover over random elements
            elements = await self.page.query_selector_all('div, span, a, img')
            if elements:
                for _ in range(random.randint(1, 3)):
                    random_element = random.choice(elements)
                    try:
                        await random_element.hover()
                        await asyncio.sleep(random.uniform(0.2, 0.7))
                    except Exception:
                        pass
        
        except Exception as e:
            logger.warning(f"Error in human-like interactions: {str(e)}")

    async def _handle_403_error(self, url):
        """Handle 403 Forbidden errors with advanced retry techniques"""
        logger.warning(f"Encountered 403 Forbidden at {url}. Attempting recovery...")
        
        # Take screenshot of the 403 error
        await self.page.screenshot(path=f"{config.screenshots_dir}/403_error.png")
        
        recovery_techniques = [
            self._retry_with_new_user_agent,
            self._retry_with_new_cookies,
            self._retry_with_referrer,
            self._retry_with_delay,
            self._retry_with_new_context,
            self._retry_with_mobile_agent
        ]
        
        # Try each recovery technique in sequence until one works
        for i, technique in enumerate(recovery_techniques):
            logger.info(f"Trying 403 recovery technique {i+1}/{len(recovery_techniques)}")
            if await technique(url):
                logger.info(f"Successfully recovered from 403 error using technique {i+1}")
                return True
        
        logger.error("All 403 recovery techniques failed")
        return False

    async def _retry_with_new_user_agent(self, url):
        """Retry with a different user agent"""
        try:
            logger.info("Retrying with new user agent")
            new_user_agent = config.get_random_user_agent()
            await self.page.set_extra_http_headers({
                'User-Agent': new_user_agent
            })
            
            response = await self.page.goto(url, wait_until="domcontentloaded")
            return response.status != 403
        except Exception as e:
            logger.warning(f"Error retrying with new user agent: {str(e)}")
            return False

    async def _retry_with_new_cookies(self, url):
        """Clear cookies and retry"""
        try:
            logger.info("Clearing cookies and retrying")
            await self.context.clear_cookies()
            # Try to load saved cookies again
            if os.path.exists(config.cookies_path):
                with open(config.cookies_path, 'r') as f:
                    cookies = json.load(f)
                    await self.context.add_cookies(cookies)
            
            # Add a short delay to avoid immediate retry
            await asyncio.sleep(random.uniform(2.0, 4.0))
            response = await self.page.goto(url, wait_until="domcontentloaded")
            return response.status != 403
        except Exception as e:
            logger.warning(f"Error retrying with new cookies: {str(e)}")
            return False

    async def _retry_with_referrer(self, url):
        """Retry with a legitimate referrer header"""
        try:
            logger.info("Retrying with legitimate referrer")
            referrers = [
                'https://www.baidu.com/s?wd=京东',
                'https://www.sogou.com/web?query=京东商城',
                'https://www.google.com/search?q=jd.com',
                'https://www.bing.com/search?q=jd.com+购物'
            ]
            
            await self.page.set_extra_http_headers({
                'Referer': random.choice(referrers)
            })
            
            response = await self.page.goto(url, wait_until="domcontentloaded")
            return response.status != 403
        except Exception as e:
            logger.warning(f"Error retrying with referrer: {str(e)}")
            return False

    async def _retry_with_delay(self, url):
        """Retry after a significant delay"""
        try:
            delay = random.uniform(5.0, 10.0)
            logger.info(f"Waiting {delay:.1f}s before retrying")
            await asyncio.sleep(delay)
            
            # Clear navigation history
            await self.page.evaluate("window.history.pushState({}, '', 'about:blank')")
            
            response = await self.page.goto(url, wait_until="domcontentloaded")
            return response.status != 403
        except Exception as e:
            logger.warning(f"Error retrying with delay: {str(e)}")
            return False

    async def _retry_with_new_context(self, url):
        """Create a completely new browser context and retry"""
        try:
            logger.info("Creating new browser context")
            
            # Close current context
            if self.context and not self.context.is_closed():
                await self.context.close()
            
            # Create new context with different settings
            self.context = await self.browser.new_context(
                viewport={'width': random.randint(1200, 1400), 'height': random.randint(800, 900)},
                user_agent=config.get_random_user_agent(),
                locale='zh-CN',
                timezone_id='Asia/Shanghai',
                has_touch=random.choice([True, False])
            )
            
            # Load cookies
            await self._load_cookies()
            
            # Create new page
            self.page = await self.context.new_page()
            self.page.set_default_navigation_timeout(config.navigation_timeout)
            self.page.set_default_timeout(config.action_timeout)
            
            # Add simulated user gesture
            await self.page.evaluate("""
            () => {
                window.addEventListener('DOMContentLoaded', () => {
                    document.body && document.body.dispatchEvent(new MouseEvent('click', {
                        view: window,
                        bubbles: true,
                        cancelable: true
                    }));
                });
            }
            """)
            
            # Try accessing the URL
            response = await self.page.goto(url, wait_until="domcontentloaded")
            return response.status != 403
        except Exception as e:
            logger.warning(f"Error creating new context: {str(e)}")
            return False

    async def _retry_with_mobile_agent(self, url):
        """Try with mobile user agent"""
        try:
            logger.info("Retrying with mobile user agent")
            
            # Use a mobile URL variant if available
            mobile_url = url
            if "jd.com" in url:
                # Try to convert to mobile URL
                if "cart" in url:
                    mobile_url = random.choice(config.alternative_urls["mobile_cart"])
                elif "www.jd.com" in url:
                    mobile_url = url.replace("www.jd.com", "m.jd.com")
            
            # Set mobile viewport and user agent
            await self.page.set_viewport_size({"width": 375, "height": 812})
            await self.page.set_extra_http_headers({
                'User-Agent': config.get_random_user_agent(mobile=True)
            })
            
            # Try accessing with mobile configuration
            response = await self.page.goto(mobile_url, wait_until="domcontentloaded")
            return response.status != 403
        except Exception as e:
            logger.warning(f"Error retrying with mobile agent: {str(e)}")
            return False

    async def _try_direct_cart_access(self) -> bool:
        """Try direct access to cart URL with 403 handling"""
        try:
            logger.info(f"Trying direct cart access: {config.cart_url}")
            
            # Use response object to check for status codes
            response = await self.page.goto(config.cart_url, wait_until="domcontentloaded")
            
            # Check for 403 error by status code
            if response.status == 403:
                logger.warning("Received 403 Forbidden status code")
                if await self._handle_403_error(config.cart_url):
                    logger.info("Successfully recovered from 403 error")
                    # Verify we're on cart page after recovery
                    cart_title = await self.page.query_selector('.cart-title')
                    empty_cart = await self.page.query_selector('.empty-cart')
                    if cart_title or empty_cart:
                        logger.info("Successfully on cart page after 403 recovery")
                        await self.page.screenshot(path=f"{config.screenshots_dir}/cart_after_403_recovery.png")
                        return True
                return False
            
            await asyncio.sleep(config.wait_after_navigation)
            
            # Check for 403 error in several ways
            content = await self.page.content()
            if "403 Forbidden" in content or "拒绝了您的请求" in content:
                logger.warning("403 Forbidden detected in page content")
                return await self._handle_403_error(config.cart_url)
            
            # Check for 403 error element
            forbidden_element = await self.page.query_selector("text=403") or await self.page.query_selector("text=Forbidden")
            if forbidden_element:
                logger.warning("403 Forbidden element detected")
                return await self._handle_403_error(config.cart_url)
            
            # Check if cart page loaded successfully
            cart_title = await self.page.query_selector('.cart-title')
            if cart_title:
                logger.info("Successfully navigated to cart via direct URL")
                # Take screenshot
                await self.page.screenshot(path=f"{config.screenshots_dir}/cart_page_direct.png")
                return True
            
            # Check for empty cart page (still success)
            empty_cart = await self.page.query_selector('.empty-cart')
            if empty_cart:
                logger.info("Successfully navigated to cart (empty cart)")
                await self.page.screenshot(path=f"{config.screenshots_dir}/cart_empty.png")
                return True
            
            logger.warning("Direct cart access failed - unknown page structure")
            return False
            
        except Exception as e:
            logger.error(f"Error in direct cart access: {str(e)}")
            return False
    
    async def _try_homepage_cart_link(self) -> bool:
        """Try accessing cart via homepage cart icon link"""
        try:
            logger.info("Trying to access cart via homepage cart icon")
            
            # Try to find and click the cart link/icon
            # Try multiple selectors since JD's selectors might change
            cart_selectors = [
                "a[href*='cart.jd.com']",
                ".shopping-cart",
                "#settleup",
                ".cart-icon",
                "//a[contains(text(), '购物车')]",  # XPath for text containing "cart"
                "//a[contains(text(), '我的购物车')]"
            ]
            
            for selector in cart_selectors:
                try:
                    cart_element = await self.page.query_selector(selector)
                    if cart_element:
                        logger.info(f"Found cart element with selector: {selector}")
                        # Hover first (more human-like)
                        await cart_element.hover()
                        await asyncio.sleep(random.uniform(0.3, 0.8))
                        await cart_element.click()
                        await asyncio.sleep(config.wait_after_navigation)
                        
                        # Check if cart page loaded
                        cart_title = await self.page.query_selector('.cart-title')
                        if cart_title:
                            logger.info("Successfully navigated to cart via homepage link")
                            await self.page.screenshot(path=f"{config.screenshots_dir}/cart_page_via_link.png")
                            return True
                            
                        # Check for empty cart
                        empty_cart = await self.page.query_selector('.empty-cart')
                        if empty_cart:
                            logger.info("Successfully navigated to cart via homepage link (empty cart)")
                            await self.page.screenshot(path=f"{config.screenshots_dir}/cart_empty_via_link.png")
                            return True
                except Exception as e:
                    logger.warning(f"Error with cart selector {selector}: {str(e)}")
                    continue
            
            logger.warning("No working cart link found on homepage")
            return False
                
        except Exception as e:
            logger.error(f"Error accessing cart via homepage: {str(e)}")
            return False
            
    async def _try_minicart_access(self) -> bool:
        """Try accessing cart via mini cart popup"""
        try:
            logger.info("Trying to access cart via mini cart popup")
            
            # First try to find and hover the mini cart trigger
            mini_cart_triggers = [
                "#settleup",
                ".dorpdown",
                ".cw-icon",
                "//div[contains(@class, 'dropdown')][contains(., '购物车')]"
            ]
            
            for trigger in mini_cart_triggers:
                try:
                    mini_cart = await self.page.query_selector(trigger)
                    if mini_cart:
                        logger.info(f"Found mini cart trigger with selector: {trigger}")
                        # Hover to trigger the dropdown
                        await mini_cart.hover()
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        
                        # Look for "go to cart" link in the popup
                        cart_link_selectors = [
                            ".dropdown-content a[href*='cart']",
                            "//a[contains(text(), '去购物车')]",
                            "//a[contains(text(), '去我的购物车')]",
                            ".dorpdown-layer a"
                        ]
                        
                        for link_selector in cart_link_selectors:
                            try:
                                cart_link = await self.page.query_selector(link_selector)
                                if cart_link:
                                    logger.info(f"Found cart link in dropdown: {link_selector}")
                                    await cart_link.click()
                                    await asyncio.sleep(config.wait_after_navigation)
                                    
                                    # Check if cart page loaded
                                    cart_title = await self.page.query_selector('.cart-title')
                                    if cart_title:
                                        logger.info("Successfully navigated to cart via mini cart popup")
                                        await self.page.screenshot(path=f"{config.screenshots_dir}/cart_page_via_popup.png")
                                        return True
                                        
                                    # Check for empty cart
                                    empty_cart = await self.page.query_selector('.empty-cart')
                                    if empty_cart:
                                        logger.info("Successfully navigated to cart via mini cart popup (empty cart)")
                                        await self.page.screenshot(path=f"{config.screenshots_dir}/cart_empty_via_popup.png")
                                        return True
                            except Exception:
                                continue
                except Exception:
                    continue
            
            logger.warning("Mini cart popup access failed")
            return False
                
        except Exception as e:
            logger.error(f"Error accessing cart via mini cart: {str(e)}")
            return False
            
    async def _try_alternate_cart_url(self) -> bool:
        """Try alternative cart URLs"""
        try:
            alternate_urls = [
                "https://cart.jd.com/cart_index",
                "https://cart.jd.com/addToCart.html",
                "https://cart.jd.com/cart/cart.action",
                "https://p.m.jd.com/cart/cart.action",
                "https://cart-m.jd.com"
            ]
            
            for url in alternate_urls:
                logger.info(f"Trying alternative cart URL: {url}")
                await self.page.goto(url)
                await asyncio.sleep(config.wait_after_navigation)
                
                # Check for 403 error
                content = await self.page.content()
                if "403 Forbidden" in content or "拒绝了您的请求" in content:
                    logger.warning(f"403 Forbidden detected at {url}")
                    continue
                
                # Check if cart page loaded successfully by various indicators
                cart_indicators = [
                    '.cart-title',
                    '.cart-warp',
                    '.cart-list',
                    '.empty-cart',
                    "//div[contains(@class, 'cart')]",
                    "//h2[contains(text(), '购物车')]"
                ]
                
                for indicator in cart_indicators:
                    cart_element = await self.page.query_selector(indicator)
                    if cart_element:
                        logger.info(f"Cart indicator found at {url}: {indicator}")
                        # Update the working URL in config
                        config.cart_url = url
                        await self.page.screenshot(path=f"{config.screenshots_dir}/cart_page_alternate.png")
                        return True
            
            logger.warning("All alternative cart URLs failed")
            return False
                
        except Exception as e:
            logger.error(f"Error trying alternative cart URLs: {str(e)}")
            return False

    async def _try_mobile_cart_access(self) -> bool:
        """Try accessing cart via JD's mobile site"""
        try:
            logger.info("Trying mobile cart access")
            
            # Set mobile user agent temporarily
            mobile_agents = [
                "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/93.0.4577.63 Mobile/15E148 Safari/604.1"
            ]
            
            # Temporarily change user agent to mobile
            original_user_agent = await self.page.evaluate('() => navigator.userAgent')
            await self.context.clear_cookies()  # Clear cookies to avoid detection
            
            # Create a new mobile context
            mobile_context = await self.browser.new_context(
                viewport={'width': 375, 'height': 812},
                user_agent=random.choice(mobile_agents),
                is_mobile=True,
                has_touch=True
            )
            
            try:
                # Load cookies into the mobile context
                with open(config.cookies_path, 'r') as f:
                    cookies = json.load(f)
                    await mobile_context.add_cookies(cookies)
                
                mobile_page = await mobile_context.new_page()
                
                # Try several mobile cart URLs
                mobile_urls = [
                    "https://p.m.jd.com/cart/cart.action",
                    "https://cart-m.jd.com",
                    "https://wq.jd.com/cart/view",
                    "https://wqs.jd.com/my/cart.shtml"
                ]
                
                for url in mobile_urls:
                    logger.info(f"Trying mobile cart URL: {url}")
                    await mobile_page.goto(url, wait_until="domcontentloaded")
                    await asyncio.sleep(random.uniform(2.0, 3.0))
                    
                    # Check if we need verification
                    verification = await mobile_page.query_selector('[class*="verify"]')
                    if verification:
                        logger.warning("Verification required on mobile site")
                        await mobile_page.screenshot(path=f"{config.screenshots_dir}/mobile_verification.png")
                        # If we need verification, restart with our normal browser
                        break
                    
                    # Check for cart indicators on mobile site
                    cart_indicators = [
                        '[class*="cart"]',
                        '[class*="shopping"]',
                        "//div[contains(text(), '购物车')]"
                    ]
                    
                    for indicator in cart_indicators:
                        try:
                            element = await mobile_page.query_selector(indicator)
                            if element:
                                # Found cart page on mobile
                                await mobile_page.screenshot(path=f"{config.screenshots_dir}/mobile_cart.png")
                                
                                # Extract cart URL and switch back to desktop
                                mobile_cart_url = mobile_page.url
                                await mobile_context.close()
                                
                                # Try to use the same URL in our main desktop browser
                                await self.page.goto(mobile_cart_url)
                                await asyncio.sleep(config.wait_after_navigation)
                                
                                # If desktop version automatically redirects to cart, great!
                                desktop_cart_element = await self.page.query_selector('.cart-title, .cart-warp, .cart-list')
                                if desktop_cart_element:
                                    logger.info("Successfully navigated to desktop cart via mobile URL")
                                    return True
                                
                                # Otherwise, we at least found the mobile cart URL for future reference
                                logger.info(f"Found working mobile cart URL: {mobile_cart_url}")
                                await self.page.screenshot(path=f"{config.screenshots_dir}/mobile_cart_to_desktop.png")
                                return True
                        except Exception as e:
                            logger.debug(f"Error checking mobile indicator {indicator}: {str(e)}")
                
                await mobile_context.close()
                return False
                
            finally:
                # Clean up the mobile context
                try:
                    if mobile_context:
                        await mobile_context.close()
                except Exception:
                    pass
                    
                # Reset user agent
                try:
                    await self.page.evaluate(f'() => Object.defineProperty(navigator, "userAgent", {{ get: () => "{original_user_agent}" }})')
                except Exception:
                    pass
                
        except Exception as e:
            logger.error(f"Error trying mobile cart access: {str(e)}")
            return False

    async def checkout(self) -> bool:
        """Process checkout from cart"""
        try:
            # Ensure page is available
            if not await self._ensure_page_available():
                return False

            # Navigate to cart using our improved method
            if not await self.navigate_to_cart():
                logger.error("Failed to navigate to cart for checkout")
                return False
            
            # Check if cart has items
            empty_cart = await self.page.query_selector('.empty-cart')
            if empty_cart:
                logger.error("Cart is empty, nothing to checkout")
                return False
                
            # Add random human-like delay
            random_delay = random.uniform(0.5, 2.0)
            await asyncio.sleep(random_delay)
            
            # Select all items
            select_all = await self.page.query_selector('.jdcheckbox')
            if select_all:
                await select_all.click()
                await asyncio.sleep(0.5)
                
            # Click checkout button
            checkout_btn = await self.page.query_selector('.common-submit-btn')
            if not checkout_btn:
                logger.error("Checkout button not found")
                return False
                
            await checkout_btn.click()
            
            # Wait for checkout page
            await self.page.wait_for_selector('.order-submit')
            
            # Take screenshot of order page
            await self.page.screenshot(path=f"{config.screenshots_dir}/checkout.png")
            
            # Submit order (commented out for safety - uncomment to enable actual ordering)
            # submit_btn = await self.page.query_selector('.order-submit .btn-submit')
            # if submit_btn:
            #     await submit_btn.click()
            #     await self.page.wait_for_selector('.pay-info')
            #     await self.page.screenshot(path=f"{config.screenshots_dir}/order_placed.png")
            
            logger.info("Checkout process completed. Ready for order submission.")
            logger.warning("Order submission is disabled by default for safety. Edit the code to enable.")
            return True
            
        except Exception as e:
            logger.error(f"Error during checkout: {str(e)}")
            return False

    async def run(self):
        """Run the complete shopping process"""
        try:
            await self.setup()
            
            if not await self.login():
                logger.error("Login failed, exiting")
                return
                
            # Navigate to homepage
            logger.info("Successfully logged in, navigating to homepage")
            await self.page.goto(config.homepage_url)
            await self.page.screenshot(path=f"{config.screenshots_dir}/homepage.png")
            logger.info("Now on homepage. Session is active.")
            
            # Keep the browser open
            user_input = input("Press Enter to close the browser and exit: ")
            
        except Exception as e:
            logger.error(f"Error in process: {str(e)}")
        finally:
            await self.close()


async def main():
    """Main entry point"""
    logger.info("Starting JD Auto Buyer")
    
    # Validate credentials
    if config.username and config.password:
        logger.info("Username and password found in environment variables. Will attempt account login.")
    else:
        logger.warning("Username or password not set in environment variables. QR code login will be required.")
    
    # Check if there are food keywords to search
    if not config.search_keywords:
        logger.warning("No search keywords defined in config. Please add keywords to search.")
        search_input = input("Enter food keywords to search (separated by comma): ")
        if search_input.strip():
            config.search_keywords = [keyword.strip() for keyword in search_input.split(',')]
        else:
            logger.error("No keywords provided. Exiting.")
            return
    
    # Create and run the auto buyer
    buyer = JDAutoBuyer()
    await buyer.run()


if __name__ == "__main__":
    # Configure logger
    logger.add(
        "jd_auto_buyer.log",
        rotation="10 MB",
        retention="1 week",
        level="INFO"
    )
    
    # Run the main function
    asyncio.run(main())