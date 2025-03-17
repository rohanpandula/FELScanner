#!/usr/bin/env python3
import os
import json
import logging
import subprocess
import tempfile
import sys
from datetime import datetime
import requests
from pathlib import Path

# Ensure data directory exists before configuring logging
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(data_dir, exist_ok=True)
log_file = os.path.join(data_dir, 'log.txt')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)

logger = logging.getLogger("IPTScanner")

def ensure_data_dir(config):
    """Ensure data directory exists"""
    data_dir = config.get('dataPath', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'))
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def run(config):
    """Run the IPTScanner with the provided configuration"""
    try:
        # Make sure the data directory exists
        data_dir = ensure_data_dir(config)
        
        # Create a temporary config file for the JS script
        with tempfile.NamedTemporaryFile(suffix='.json', mode='w+', delete=False) as temp_config:
            # Convert config to the format expected by the JS script
            js_config = {
                "iptorrents": {
                    "url": "https://iptorrents.com/login",
                    "searchUrl": f"https://iptorrents.com/t?q={config.get('searchTerm', 'BL+EL+RPU')}&qf=adv#torrents",
                    "searchTerm": config.get('searchTerm', 'BL+EL+RPU'),
                    "cookiePath": ""
                },
                "telegram": {
                    "enabled": False,  # Disable Telegram notifications when run from the web interface
                    "botToken": "",
                    "chatId": ""
                },
                "checkInterval": "0 */2 * * *",  # Default to every 2 hours
                "dataPath": os.path.join(data_dir, "known_torrents.json"),
                "configPath": os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
                "cookiesPath": os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.json"),
                "headless": config.get('headless', True),
                "debug": config.get('debug', False),
                "loginComplete": False,
                "userDataDir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser-profile"),
                "lastUpdateTime": datetime.now().isoformat(),
                "oneTimeRun": True  # Always use one-time mode when run from the web interface
            }
            
            # Write the config to the temp file
            json.dump(js_config, temp_config)
            temp_config.flush()
            
            # Run the JS script with the temp config
            js_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor-iptorrents.js")
            cmd = ["node", js_script, "--config", temp_config.name, "--one-time"]
            
            logger.info(f"Running command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            stdout, stderr = process.communicate()
            
            # Log the output
            if stdout:
                for line in stdout.splitlines():
                    if line.strip():
                        logger.info(f"JS: {line}")
            
            if stderr:
                for line in stderr.splitlines():
                    if line.strip():
                        logger.error(f"JS Error: {line}")
            
            if process.returncode != 0:
                logger.error(f"JS script exited with code {process.returncode}")
                return False
            
            logger.info("JS script completed successfully")
            return True
    except Exception as e:
        logger.exception(f"Error running IPTScanner: {str(e)}")
        return False
    finally:
        # Clean up temp config file
        if 'temp_config' in locals() and os.path.exists(temp_config.name):
            os.unlink(temp_config.name)

def test_login(uid, passkey):
    """Test if the provided cookies are valid for IPTorrents login"""
    try:
        # Use environment variables if available
        env_uid = os.environ.get('IPT_UID')
        env_pass = os.environ.get('IPT_PASS')
        
        if env_uid and env_pass:
            uid = env_uid
            passkey = env_pass
            logger.info("Using IPTorrents credentials from environment variables")
        
        # Make sure we have the first few characters for logging but not the full credentials
        uid_prefix = uid[:3] if len(uid) > 3 else "***"
        passkey_prefix = passkey[:3] if len(passkey) > 3 else "***"
        logger.info(f"Testing login with UID: {uid_prefix}*** and passkey: {passkey_prefix}***")
        
        # Create cookies file
        cookies = [
            {
                "name": "uid",
                "value": uid,
                "domain": ".iptorrents.com",
                "path": "/",
                "expires": int(datetime.now().timestamp() + 86400 * 30)
            },
            {
                "name": "pass",
                "value": passkey,
                "domain": ".iptorrents.com",
                "path": "/",
                "expires": int(datetime.now().timestamp() + 86400 * 30)
            }
        ]
        
        cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.json')
        with open(cookies_path, 'w') as f:
            json.dump(cookies, f)
            logger.info(f"Saved cookies to {cookies_path}")
        
        # Use requests to test the login with the cookies
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'].lstrip('.'))
        
        logger.info("Attempting to access IPTorrents member page")
        
        # Try to access member page
        response = session.get('https://iptorrents.com/t', allow_redirects=False)
        
        # If response is redirect to login page, login failed
        if response.status_code in [301, 302]:
            redirect_url = response.headers.get('Location', '')
            logger.warning(f"Login test failed: Redirected to {redirect_url}")
            if 'login' in redirect_url:
                return False
        
        # Check for the logout link on the page
        if response.status_code == 200:
            logger.info("Got 200 response from IPTorrents")
            if 'logout' in response.text.lower():
                logger.info("Login test successful - found logout link")
                
                # Save credentials to config
                config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
                try:
                    if os.path.exists(config_path):
                        with open(config_path, 'r') as f:
                            config = json.load(f)
                            
                        # Update config with new credentials
                        config['uid'] = uid
                        config['pass'] = passkey
                        
                        with open(config_path, 'w') as f:
                            json.dump(config, f, indent=2)
                            logger.info("Updated config with new credentials")
                except Exception as e:
                    logger.error(f"Error updating config with credentials: {str(e)}")
                
                return True
            else:
                logger.warning("No logout link found on page - login likely failed")
        
        logger.warning(f"Login test failed with status code: {response.status_code}")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error while testing login: {str(e)}")
        return False
    except Exception as e:
        logger.exception(f"Error testing login: {str(e)}")
        return False

if __name__ == "__main__":
    # Test run with default config
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
        run(config)
    else:
        print("Config file not found. Create one or specify config path.") 