#!/usr/bin/env python3
"""
PM Watchman Quick Setup Script

Automated setup script to help new users quickly configure their PM job search system.
Guides through environment setup, Telegram bot creation, and basic configuration.
"""

import os
import sys
import subprocess
import json
from pathlib import Path


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}{Colors.ENDC}\n")


def print_success(text):
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_warning(text):
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def print_error(text):
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_info(text):
    print(f"{Colors.OKBLUE}ℹ️  {text}{Colors.ENDC}")


def check_python_version():
    """Check if Python 3.9+ is installed."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} detected")
        return True
    else:
        print_error(f"Python 3.9+ required. Found {version.major}.{version.minor}.{version.micro}")
        return False


def setup_virtual_environment():
    """Create and activate virtual environment."""
    try:
        if not os.path.exists('venv'):
            print_info("Creating virtual environment...")
            subprocess.run([sys.executable, '-m', 'venv', 'venv'], check=True)
            print_success("Virtual environment created")
        else:
            print_success("Virtual environment already exists")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to create virtual environment")
        return False


def install_dependencies():
    """Install required Python packages."""
    try:
        # Determine the correct pip path based on OS
        if os.name == 'nt':  # Windows
            pip_path = 'venv\\Scripts\\pip'
        else:  # macOS/Linux
            pip_path = 'venv/bin/pip'
        
        print_info("Installing dependencies...")
        subprocess.run([pip_path, 'install', '-r', 'requirements.txt'], check=True)
        print_success("Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to install dependencies")
        return False


def get_telegram_credentials():
    """Guide user through Telegram bot setup."""
    print_header("TELEGRAM BOT SETUP")
    
    print("📱 Follow these steps to create your Telegram bot:")
    print("1. Open Telegram and search for @BotFather")
    print("2. Send /newbot command")
    print("3. Choose a name for your bot (e.g., 'John PM Job Search')")
    print("4. Choose a username (e.g., 'john_pm_job_bot')")
    print("5. Copy the bot token (format: 1234567890:ABC...)")
    print("\n6. Start your bot by sending /start")
    print("7. Get your Chat ID by messaging @userinfobot with any text")
    print("8. Copy your Chat ID (format: 123456789)")
    
    print(f"\n{Colors.WARNING}Make sure to complete these steps before continuing!{Colors.ENDC}")
    input("\nPress Enter when you have both the bot token and chat ID...")
    
    bot_token = input("\nEnter your bot token: ").strip()
    chat_id = input("Enter your chat ID: ").strip()
    
    if not bot_token or not chat_id:
        print_error("Both bot token and chat ID are required")
        return None, None
    
    # Basic validation
    if ':' not in bot_token or len(chat_id) < 5:
        print_warning("Credentials format looks unusual. Please double-check.")
    
    return bot_token, chat_id


def create_env_file(bot_token, chat_id):
    """Create .env file with user credentials."""
    try:
        env_content = f"""# Telegram Configuration
TELEGRAM_BOT_TOKEN={bot_token}
TELEGRAM_CHAT_ID={chat_id}

# System Configuration
LOG_LEVEL=INFO
ENVIRONMENT=local
DEBUG_MODE=false
"""
        
        with open('.env', 'w') as f:
            f.write(env_content)
        
        print_success("Environment file created")
        return True
    except Exception as e:
        print_error(f"Failed to create .env file: {e}")
        return False


def create_sample_pm_profile():
    """Create a sample PM profile for the user to customize."""
    profile = {
        "meta": {
            "version": "1.0",
            "last_updated": "2025-01-15",
            "description": "Personal PM profile for job matching - CUSTOMIZE THIS!"
        },
        "experience": {
            "years_of_pm_experience": "CHANGE_ME: 1-15+",
            "current_title": "CHANGE_ME: Your current role",
            "seniority_level": "CHANGE_ME: junior|mid|senior|principal|director"
        },
        "target_roles": {
            "primary_titles": ["Product Manager", "Senior Product Manager"],
            "secondary_titles": ["Product Owner", "Product Lead"],
            "avoid_titles": ["Sales", "Marketing Manager"]
        },
        "skills": {
            "core_pm_skills": ["product strategy", "roadmapping", "user research", "data analysis"],
            "technical_skills": ["SQL", "analytics tools", "figma", "jira"],
            "domain_expertise": ["B2B SaaS", "mobile apps", "web platforms"]
        },
        "industries": {
            "primary_experience": ["technology", "software"],
            "interested_in": ["fintech", "healthtech"],
            "avoid_industries": ["gambling", "tobacco"]
        },
        "geographic_preferences": {
            "remote_preference": "remote_first",
            "preferred_locations": ["Remote", "San Francisco", "New York"],
            "acceptable_commute": "30 minutes"
        },
        "company_preferences": {
            "company_stages": ["startup", "growth"],
            "company_sizes": ["51-200", "201-500"],
            "preferred_companies": ["Stripe", "Notion", "Linear"]
        },
        "compensation": {
            "minimum_base_salary": 120000,
            "target_total_comp": 180000,
            "equity_importance": "high"
        }
    }
    
    try:
        os.makedirs('config', exist_ok=True)
        with open('config/pm_profile.json', 'w') as f:
            json.dump(profile, f, indent=2)
        
        print_success("Sample PM profile created at config/pm_profile.json")
        print_warning("⚠️  IMPORTANT: Edit config/pm_profile.json with your actual information!")
        return True
    except Exception as e:
        print_error(f"Failed to create PM profile: {e}")
        return False


def create_basic_configs():
    """Create basic system settings and job sources."""
    
    # System settings
    system_settings = {
        "scheduling": {
            "jobs_per_batch": 10,
            "batches_per_day": 4,
            "hours_between_batches": 6,
            "preferred_start_hour": 9,
            "timezone": "America/Los_Angeles"
        },
        "scoring": {
            "minimum_score_threshold": 60,
            "title_match_importance": "high",
            "skills_match_importance": "high",
            "experience_match_importance": "medium",
            "industry_match_importance": "medium",
            "company_match_importance": "low"
        },
        "telegram": {
            "message_formatting": {
                "jobs_per_message": 1,
                "include_description_preview": True,
                "max_description_length": 200
            },
            "delivery_settings": {
                "retry_attempts": 3,
                "retry_delay_seconds": 5
            }
        }
    }
    
    # Job sources
    job_sources = {
        "linkedin": {
            "enabled": True,
            "priority": 1,
            "search_parameters": {
                "job_titles": ["Product Manager", "Senior Product Manager"],
                "locations": ["Remote", "San Francisco", "New York"],
                "date_posted": "past_24_hours"
            }
        },
        "rss_feeds": {
            "primary_sources": {
                "wework_remotely": {
                    "url": "https://weworkremotely.com/categories/remote-product-jobs.rss",
                    "enabled": True,
                    "priority": 2
                },
                "remotive": {
                    "url": "https://remotive.com/feed",
                    "enabled": True,
                    "priority": 2
                }
            }
        }
    }
    
    try:
        with open('config/system_settings.json', 'w') as f:
            json.dump(system_settings, f, indent=2)
        
        with open('config/job_sources.json', 'w') as f:
            json.dump(job_sources, f, indent=2)
        
        print_success("Basic configuration files created")
        return True
    except Exception as e:
        print_error(f"Failed to create config files: {e}")
        return False


def test_installation():
    """Test the installation by verifying imports."""
    try:
        # Determine the correct python path based on OS
        if os.name == 'nt':  # Windows
            python_path = 'venv\\Scripts\\python'
        else:  # macOS/Linux
            python_path = 'venv/bin/python'
        
        test_command = [
            python_path, '-c',
            'import feedparser, requests, telegram; from dotenv import load_dotenv; print("✅ All imports successful")'
        ]
        
        result = subprocess.run(test_command, capture_output=True, text=True)
        
        if result.returncode == 0:
            print_success("Installation test passed")
            return True
        else:
            print_error(f"Installation test failed: {result.stderr}")
            return False
    except Exception as e:
        print_error(f"Failed to run installation test: {e}")
        return False


def main():
    """Main setup process."""
    print_header("PM WATCHMAN QUICK SETUP")
    print("🤖 Setting up your automated PM job search system...")
    
    # Step 1: Check Python
    print_header("STEP 1: CHECKING PYTHON")
    if not check_python_version():
        sys.exit(1)
    
    # Step 2: Virtual Environment
    print_header("STEP 2: VIRTUAL ENVIRONMENT")
    if not setup_virtual_environment():
        sys.exit(1)
    
    # Step 3: Dependencies
    print_header("STEP 3: INSTALLING DEPENDENCIES")
    if not install_dependencies():
        sys.exit(1)
    
    # Step 4: Telegram Setup
    bot_token, chat_id = get_telegram_credentials()
    if not bot_token or not chat_id:
        sys.exit(1)
    
    # Step 5: Environment File
    print_header("STEP 5: CREATING ENVIRONMENT FILE")
    if not create_env_file(bot_token, chat_id):
        sys.exit(1)
    
    # Step 6: Configuration Files
    print_header("STEP 6: CREATING CONFIGURATION FILES")
    if not create_sample_pm_profile():
        sys.exit(1)
    
    if not create_basic_configs():
        sys.exit(1)
    
    # Step 7: Test Installation
    print_header("STEP 7: TESTING INSTALLATION")
    if not test_installation():
        sys.exit(1)
    
    # Success!
    print_header("🎉 SETUP COMPLETE!")
    print_success("Your PM Watchman system is ready!")
    
    print(f"\n{Colors.BOLD}Next Steps:{Colors.ENDC}")
    print("1. ⚠️  Edit config/pm_profile.json with your actual PM experience")
    print("2. 📝 Customize config/job_sources.json if needed")
    print("3. 🚀 Test run: python main.py --test")
    print("4. 📅 Set up cron job for automation")
    
    print(f"\n{Colors.OKGREEN}Your system will discover 40+ PM jobs daily and send them via Telegram!{Colors.ENDC}")


if __name__ == "__main__":
    main()