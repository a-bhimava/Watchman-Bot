# 🚀 PM Watchman - User Setup Guide

Complete guide for setting up your personal PM job search automation system.

## 📋 Prerequisites (5 minutes)

Before starting, ensure you have:
- **Python 3.9+** installed ([Download here](https://python.org))
- **Telegram account** (free mobile app)
- **Internet connection** for RSS feeds and Telegram
- **15-20 minutes** for complete setup

## 🎯 Quick Setup (Recommended)

### Option 1: Automated Setup Script

1. **Clone/Download the Repository**
   ```bash
   # If using GitHub template (recommended):
   # Click "Use this template" button on GitHub
   
   # Or clone directly:
   git clone https://github.com/a-bhimava/pm-watchman.git
   cd pm-watchman
   ```

2. **Run the Setup Script**
   ```bash
   python3 scripts/quick_setup.py
   ```

   The script will:
   - ✅ Check Python version
   - ✅ Create virtual environment
   - ✅ Install dependencies
   - ✅ Guide you through Telegram bot creation
   - ✅ Create configuration files
   - ✅ Test the installation

3. **Follow the Telegram Bot Setup**
   
   When prompted by the script:
   
   **Create Bot:**
   - Open Telegram → Search `@BotFather`
   - Send `/newbot`
   - Name: `[YourName] PM Job Search`
   - Username: `[yourname]_pm_job_bot`
   - **Copy the bot token** (format: `1234567890:ABC...`)

   **Get Chat ID:**
   - Send `/start` to your new bot
   - Message `@userinfobot` with any text
   - **Copy your chat ID** (format: `123456789`)

4. **Customize Your Profile**
   
   **IMPORTANT**: Edit `config/pm_profile.json` with your actual information:
   ```bash
   # Open in your preferred editor
   nano config/pm_profile.json
   # or
   code config/pm_profile.json
   ```
   
   Update these key sections:
   - **Experience**: Years of PM experience, current title, seniority
   - **Skills**: Product strategy, analytics tools, technical skills
   - **Industries**: Fintech, SaaS, healthcare, etc.
   - **Location**: Remote preference, cities
   - **Salary**: Minimum and target compensation
   - **Companies**: Preferred and avoid lists

5. **Test Your System**
   ```bash
   python main.py --test
   ```
   
   You should receive a Telegram message with test jobs!

---

## 🛠️ Manual Setup (Alternative)

### Step 1: Environment Setup
```bash
# Create project directory
mkdir pm-watchman && cd pm-watchman

# Download/clone the code
# ... (get the files)

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Telegram Bot Setup
1. Create bot via @BotFather (see instructions above)
2. Get your chat ID via @userinfobot
3. Create `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

### Step 3: Configuration
1. Copy and customize configuration files:
   ```bash
   # Create your PM profile
   cp examples/sample_pm_profile.json config/pm_profile.json
   # Edit with your information
   
   # Use default system settings (or customize)
   cp examples/sample_config.json config/system_settings.json
   ```

---

## ⚙️ Configuration Guide

### PM Profile Configuration (`config/pm_profile.json`)

**Critical fields to customize:**

```json
{
  "experience": {
    "years_of_pm_experience": 3,  // Your actual years
    "current_title": "Product Manager",
    "seniority_level": "mid"  // junior|mid|senior|principal|director
  },
  
  "target_roles": {
    "primary_titles": [
      "Product Manager", 
      "Senior Product Manager"
    ],
    "avoid_titles": ["Sales Manager", "Marketing Manager"]
  },
  
  "skills": {
    "core_pm_skills": [
      "product strategy", "roadmapping", "user research", 
      "data analysis", "A/B testing"
    ],
    "technical_skills": ["SQL", "Python", "Figma", "Jira"]
  },
  
  "industries": {
    "primary_experience": ["SaaS", "fintech"],
    "interested_in": ["healthtech", "edtech"],
    "avoid_industries": ["gambling", "tobacco"]
  },
  
  "geographic_preferences": {
    "remote_preference": "remote_first",  // remote_only|remote_first|hybrid|onsite
    "preferred_locations": ["Remote", "San Francisco", "Austin"]
  },
  
  "compensation": {
    "minimum_base_salary": 120000,
    "target_total_comp": 180000
  }
}
```

### System Settings (`config/system_settings.json`)

**Default settings work for most users**, but you can customize:

- **Batch timing**: How often you receive jobs
- **Scoring weights**: What matters most in job matching
- **Telegram formatting**: How messages look

---

## 🚀 Running Your System

### Test Mode (First Run)
```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Test run (single batch)
python main.py --test
```

**Expected result**: Telegram message with 5-10 sample jobs

### Production Mode (Continuous Operation)
```bash
# Single batch run
python main.py

# Set up automation (runs every 6 hours)
crontab -e
# Add this line (adjust path):
0 9,15,21,3 * * * cd /path/to/pm-watchman && /path/to/pm-watchman/venv/bin/python main.py
```

---

## 📱 What to Expect

### Daily Operation:
- **40-60 PM jobs** discovered daily
- **4 batches** of 10 jobs each (every 6 hours)
- **Only relevant jobs** (score ≥60) delivered
- **No duplicates** within 30 days
- **Rich formatting** with scores and explanations

### Telegram Messages:
```
🎯 Senior Product Manager (Score: 87/100)
🏢 Stripe
📍 Remote | 💰 $160k-220k

📝 Why it matches:
• Perfect title match (+30 pts)
• 5 skills matched (+15 pts)
• Fintech experience preferred (+15 pts)
• Remote work available (+5 pts)

📄 Job Preview:
"We're looking for a Senior PM to lead our payments product. You'll work with engineering and design to build features used by millions..."

🔗 [Apply Now](https://jobs.stripe.com/...)
```

---

## 🔧 Troubleshooting

### Common Issues:

**No jobs received:**
- Check internet connection
- Verify Telegram bot token in `.env`
- Test with `python main.py --test`
- Check if scoring threshold is too high

**Bot not responding:**
- Verify chat ID is correct
- Send `/start` to your bot first
- Check bot token format

**Import errors:**
- Ensure virtual environment is activated
- Reinstall: `pip install -r requirements.txt`

**Low job relevance:**
- Update `config/pm_profile.json` with more accurate info
- Adjust scoring weights in `config/system_settings.json`

---

## 🎯 Success Metrics

After setup, you should achieve:
- **25+ job applications possible daily**
- **>70 average job relevance score**
- **Zero duplicate notifications**
- **<15 minutes weekly maintenance**

---

## 📞 Getting Help

1. **Check the logs**: `data/logs/` for error messages
2. **Test individual components**: Use `--test` mode
3. **Review configuration**: Ensure all fields are correctly filled
4. **GitHub Issues**: Report problems on the repository

---

## 🎉 You're Ready!

Your PM job search system will now:
- ✅ Run autonomously for months
- ✅ Discover jobs from LinkedIn + RSS feeds  
- ✅ Score based on your preferences
- ✅ Deliver via clean Telegram notifications
- ✅ Enable 25+ applications daily

Focus on applying to jobs and landing your next PM role! 🚀