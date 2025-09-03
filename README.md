# PM Watchman - Automated Job Search System

A reliable local application that discovers 40-50 Product Manager job postings daily, scores them against your personalized PM profile, and delivers 10 relevant jobs every 6 hours via Telegram.

## 🚀 Quick Start (15 minutes)

### For New Users:
1. **Use this template** (click green button above) or clone the repo
2. **Run the automated setup**:
   ```bash
   python3 scripts/quick_setup.py
   ```
3. **Follow the prompts** to set up your Telegram bot and PM profile
4. **Test your system**:
   ```bash
   python main.py --test
   ```

### For Your Classmates/Friends:
Share this repository as a **GitHub template** - each person gets their own private, reliable system:
- ✅ Individual Telegram bots (privacy)
- ✅ Personal PM profiles (customization) 
- ✅ Independent operation (reliability)
- ✅ 15-minute setup process

📖 **Detailed setup guide**: [`docs/USER_SETUP_GUIDE.md`](docs/USER_SETUP_GUIDE.md)

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

- **Multi-source Job Discovery**: LinkedIn + RSS feeds
- **Intelligent Scoring**: 0-100 relevance score based on your PM profile
- **Batch Delivery**: 4 batches of 10 jobs daily via Telegram
- **Duplicate Prevention**: 30-day tracking to avoid repeats
- **Local Execution**: Runs on your machine with cron automation

## Documentation

See `docs/` for detailed setup and usage instructions.