# 🎯 PM Watchman - Automated Job Discovery System

**Get 50-150+ PM jobs delivered to your Telegram every 6 hours, automatically scored and filtered for your profile.**

A personalized job discovery system that finds Product Manager opportunities from multiple LinkedIn RSS feeds and delivers the top 20 most relevant matches to your Telegram bot with a simple Apply/Dismiss interface.

## ✨ What You Get

- 📱 **50-150+ jobs discovered every 6 hours** from multiple LinkedIn RSS feeds
- 🎯 **Top 20 highest-scoring jobs** delivered to Telegram in clean HTML format
- 🏢 **Accurate company extraction** from job titles (no more "LinkedIn" as company name)
- 💼 **Simple 2-button interface** - Apply (opens job link) or Dismiss (deletes message)
- 🔄 **Fully automated** - runs 24/7 on your computer with 6-hour intervals
- 🔒 **100% private** - your data stays on your machine

## 🚀 Quick Start (15 minutes)

### Step 1: Get Your Copy
**Click the green "Use this template" button** above to create your own private repository.

### Step 2: Automated Setup
```bash
git clone https://github.com/YOUR_USERNAME/pm-watchman.git
cd pm-watchman
python3 scripts/quick_setup.py
```

### Step 3: Choose Your Domain
The setup script will ask you to choose your PM focus:
- 💰 **Fintech** (Stripe, Square, Plaid, banking, payments)
- 🏥 **Healthcare** (Epic, Teladoc, clinical, medical devices)
- 📊 **Consulting** (McKinsey, BCG, Bain, strategy, operations)  
- 🚀 **Startup** (YC companies, unicorns, 0-1 products)
- 🏢 **Enterprise** (Microsoft, Oracle, B2B SaaS)
- 🎓 **New Grad Programs** (APM, rotational programs)

### Step 4: LinkedIn RSS Setup
The system comes pre-configured with two working LinkedIn RSS feeds:
1. Primary feed: Product Manager positions across target companies
2. Secondary feed: Additional PM opportunities for broader coverage
3. System automatically collects jobs every hour from both feeds
4. **To add more feeds**: Follow instructions in `config/job_sources.json`

## 🎛️ Deep Customization

Every user gets their own personalized configuration:

**Your PM Profile** (`config/pm_profile.json`):
- Experience level and previous roles
- Technical skills and domain expertise  
- Target companies and industries
- Salary requirements and location preferences

**Job Sources** (`config/job_sources.json`):
- Your LinkedIn RSS feed (priority #1)
- Domain-specific RSS feeds
- Target company career pages
- Refresh frequencies and filtering

**Scoring System** (`config/system_settings.json`):
- Company match bonuses (+35 points for target companies)
- Keyword relevance scoring
- Experience level matching
- Location and salary filtering

## 📊 Performance Optimized

**Current Status (Recently Fixed):**
- ✅ **50-150 jobs found every 6 hours** from dual LinkedIn RSS feeds
- ✅ **Top 20 delivered** based on scoring criteria (minimum score: 50)
- ✅ **Accurate company extraction** using pattern matching for "Company hiring Role" format
- ✅ **Zero duplicates** with intelligent deduplication
- ✅ **Simple Telegram interface** with Apply/Dismiss buttons and clean HTML formatting

## 🌐 Share with Your Network

Perfect for MBA classmates, PM communities, and professional networks:

**Individual Setup** (Recommended):
- Each person runs their own system
- Complete privacy and customization  
- No shared failure points
- 15-minute automated setup

**Distribution Guide**: [`docs/DISTRIBUTION_GUIDE.md`](docs/DISTRIBUTION_GUIDE.md)

## Project Structure

```
├── src/                    # Source code
│   ├── core/              # Core system modules
│   ├── integrations/      # External service integrations
│   └── utils/             # Utility functions
├── config/                # Configuration files
├── data/                  # Data storage
│   ├── cache/            # Temporary job data
│   ├── sent/             # Sent jobs tracking
│   └── logs/             # System logs
├── tests/                 # Test suite
├── scripts/               # Utility scripts
├── docs/                  # Documentation
└── examples/              # Configuration examples
```

## Features

- **Multi-source Job Discovery**: Multiple LinkedIn RSS feeds via rss.app
- **Intelligent Scoring**: 0-100 relevance score based on your PM profile
- **Batch Delivery**: 4 batches of 20 jobs daily via Telegram (every 6 hours)
- **Duplicate Prevention**: 30-day tracking to avoid repeats
- **Local Execution**: Runs on your machine with automated scheduling

## 📚 Documentation

**Quick Start:**
- 📖 **[User Setup Guide](docs/USER_SETUP_GUIDE.md)** - Complete 15-minute setup walkthrough
- 🔗 **[LinkedIn RSS Setup](docs/LINKEDIN_RSS_SETUP.md)** - Create your personalized job search feed  
- 🚀 **[Quick Distribution Guide](docs/QUICK_DISTRIBUTION_GUIDE.md)** - Share with your network in 5 minutes

**Advanced:**
- 📤 **[Distribution Guide](docs/DISTRIBUTION_GUIDE.md)** - Comprehensive sharing strategy
- 🔧 **[Configuration Templates](config/templates/)** - Domain-specific profile examples
- 🧪 **[Testing Guide](tests/)** - Validate your system setup

## 🌟 Success Stories

**Recent Improvements (Latest Version):**
- 📈 **50-150+ jobs discovered every 6 hours** from dual LinkedIn RSS feeds
- 🏢 **Fixed company name extraction** - now shows actual companies (Appian, Stord, etc.) instead of "LinkedIn"
- 💬 **Simplified Telegram interface** - clean HTML formatting with Apply/Dismiss buttons
- ⚡ **Reliable job delivery** - fixed date parsing and message formatting issues
- 🔧 **Easy RSS feed management** - instructions provided for adding more feeds

## 🤝 Community

**Join the PM Watchman Network:**
- 💬 Share setup tips and configuration optimizations
- 🔗 Exchange job market insights across domains  
- 🚀 Collaborate on new features and improvements
- 🎯 Build professional network of PM job seekers

## 🔧 Technical Architecture

**Built for Scale and Reliability:**
```
├── Core Discovery Engine    # Multi-source job aggregation
├── Intelligent Scoring     # ML-powered relevance ranking  
├── Real-time Delivery      # Telegram bot with rich formatting
├── Data Management        # SQLite with deduplication
├── Configuration System   # JSON-based personalization
├── Health Monitoring      # Automated error detection
└── Distribution Framework # Easy sharing and customization
```

## 📊 Performance Metrics

**System Performance:**
- ⚡ **<2 second** job discovery and scoring
- 📱 **<5 second** Telegram delivery with HTML formatting
- 🔄 **Hourly collection** from multiple LinkedIn RSS feeds
- 🎯 **Top 20 jobs** delivered every 6 hours (score >= 50)
- 💾 **<50MB** memory usage
- 🔧 **Fully automated** operation with error handling

---
