"""
Telegram Bot for PM Job Delivery

Interactive Telegram bot for delivering scored PM jobs with user preferences,
filtering, and management commands.
"""

import asyncio
import json
import os
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode
import sqlite3
from contextlib import contextmanager

from integrations.rss_processor import JobData
from processing.job_enricher import EnrichedJobData
from core.default_pm_scorer import DefaultPMScorer
from core.config_loader import PMProfile, SystemSettings
from storage.job_storage import JobStorage
from utils.logger import get_logger, performance_tracker


@dataclass
class TelegramUserPreferences:
    """User preferences for job delivery."""
    user_id: int
    username: Optional[str] = None
    
    # Delivery preferences
    enabled: bool = True
    delivery_time: str = "09:00"  # HH:MM format
    timezone: str = "UTC"
    frequency: str = "daily"  # daily, twice_daily, immediate
    
    # Content preferences  
    max_jobs_per_message: int = 1
    include_description_preview: bool = True
    include_detailed_scoring: bool = False
    min_score_threshold: float = 60.0
    
    # Job filtering
    excluded_companies: List[str] = field(default_factory=list)
    required_keywords: List[str] = field(default_factory=list)
    excluded_keywords: List[str] = field(default_factory=list)
    max_daily_jobs: int = 10
    
    # Interaction settings
    enable_job_actions: bool = True  # Save, dismiss, etc.
    enable_search: bool = True
    
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class JobDelivery:
    """Record of job delivery to user."""
    id: int
    user_id: int
    job_id: str
    message_id: Optional[int] = None
    delivered_at: datetime = field(default_factory=datetime.now)
    user_action: Optional[str] = None  # saved, dismissed, applied
    action_at: Optional[datetime] = None


class TelegramMessageFormatter:
    """Formats jobs for Telegram delivery with rich formatting."""
    
    def __init__(self, pm_scorer: DefaultPMScorer):
        self.pm_scorer = pm_scorer
        self.logger = get_logger(__name__)
    
    def format_job_message(self, 
                          enriched_job: EnrichedJobData,
                          preferences: TelegramUserPreferences,
                          show_detailed_scoring: bool = False) -> tuple[str, InlineKeyboardMarkup]:
        """Format job for Telegram message with interactive buttons."""
        
        job = enriched_job.original_job
        score = getattr(enriched_job, 'pm_score', None)
        
        # Calculate score if not present
        if not score and hasattr(self, '_temp_profile_and_settings'):
            profile, settings = self._temp_profile_and_settings
            score = self.pm_scorer.score_job(job, profile, settings)
        
        # Message header with score and grade
        score_percentage = score.total_score if score else 0
        grade_emoji = self._get_grade_emoji(score_percentage)
        priority_text = self._get_priority_text(score_percentage)
        
        message = f"🎯 **PM Job Alert**\n\n"
        message += f"**{self._escape_markdown(job.title)}** at **{self._escape_markdown(job.company)}**\n"
        message += f"📍 {self._escape_markdown(job.location)}\n"
        
        # Salary information if available
        if enriched_job.extracted_salary:
            salary = enriched_job.extracted_salary
            if salary.min_salary and salary.max_salary:
                message += f"💰 ${salary.min_salary:,} - ${salary.max_salary:,}\n"
            elif salary.min_salary:
                message += f"💰 ${salary.min_salary:,}+\n"
            else:
                message += f"💰 Salary not disclosed\n"
        else:
            message += f"💰 Salary not disclosed\n"
        
        message += f"\n**Score: {score_percentage:.0f}%** | **Grade: {grade_emoji}**\n"
        message += f"**Priority: {priority_text}**\n\n"
        
        # Key details section
        message += "🔍 **Key Details:**\n"
        
        # Experience and seniority
        if enriched_job.seniority_level:
            message += f"📈 Level: {enriched_job.seniority_level.title()}\n"
        if enriched_job.experience_required:
            message += f"⏱️ Experience: {enriched_job.experience_required}\n"
        
        # Company info
        if enriched_job.company_info:
            if enriched_job.company_info.size:
                message += f"🏢 Company Size: {enriched_job.company_info.size.title()}\n"
            if enriched_job.company_info.industry:
                message += f"🏭 Industry: {enriched_job.company_info.industry.title()}\n"
        
        # Remote work type
        if enriched_job.remote_work_type and enriched_job.remote_work_type != "unknown":
            work_type_emoji = {"remote": "🏠", "hybrid": "🔀", "onsite": "🏢"}.get(enriched_job.remote_work_type, "")
            message += f"{work_type_emoji} Work Type: {enriched_job.remote_work_type.title()}\n"
        
        # Skills preview if available
        if enriched_job.extracted_skills and enriched_job.extracted_skills.pm_skills:
            top_skills = enriched_job.extracted_skills.pm_skills[:3]
            message += f"🛠️ Key Skills: {', '.join(top_skills)}\n"
        
        # Description preview
        if preferences.include_description_preview and hasattr(job, 'description') and job.description:
            preview = job.description[:200] + "..." if len(job.description) > 200 else job.description
            message += f"\n📝 **Description Preview:**\n{self._escape_markdown(preview)}\n"
        
        # Detailed scoring breakdown
        if show_detailed_scoring and score:
            message += "\n📊 **Scoring Breakdown:**\n"
            for reason in score.scoring_reasons[:5]:  # Top 5 scoring factors
                percentage = (reason.points / reason.max_points) * 100 if reason.max_points > 0 else 0
                emoji = self._get_score_emoji(percentage)
                message += f"{emoji} {reason.category.title()}: {percentage:.0f}% - {reason.explanation}\n"
        
        # Job posting date
        if job.posted_date:
            message += f"\n📅 Posted: {job.posted_date}\n"
        
        # Create interactive buttons
        keyboard = self._create_job_keyboard(job.id, preferences)
        
        return message, keyboard
    
    def format_batch_message(self, 
                           enriched_jobs: List[EnrichedJobData],
                           preferences: TelegramUserPreferences) -> tuple[str, InlineKeyboardMarkup]:
        """Format multiple jobs in a batch message."""
        
        if not enriched_jobs:
            return "No jobs found matching your criteria.", None
        
        message = f"🚀 **Daily PM Job Update**\n"
        message += f"📅 Found {len(enriched_jobs)} jobs matching your profile\n\n"
        
        for i, enriched_job in enumerate(enriched_jobs[:preferences.max_daily_jobs], 1):
            job = enriched_job.original_job
            score = getattr(enriched_job, 'pm_score', None)
            score_percentage = score.total_score if score else 0
            
            grade_emoji = self._get_grade_emoji(score_percentage)
            
            message += f"**#{i}** {grade_emoji} **{self._escape_markdown(job.title)}** at **{self._escape_markdown(job.company)}**\n"
            message += f"📍 {self._escape_markdown(job.location)} | 💯 Score: {score_percentage:.0f}%\n"
            
            # Add salary if available
            if enriched_job.extracted_salary and enriched_job.extracted_salary.min_salary:
                salary = enriched_job.extracted_salary
                if salary.min_salary and salary.max_salary:
                    message += f"💰 ${salary.min_salary:,} - ${salary.max_salary:,}\n"
                else:
                    message += f"💰 ${salary.min_salary:,}+\n"
            
            message += "\n"
        
        # Add navigation keyboard for batch
        keyboard = self._create_batch_keyboard(len(enriched_jobs))
        
        return message, keyboard
    
    def _escape_markdown(self, text: str) -> str:
        """Escape Markdown special characters."""
        if not text:
            return ""
        
        # Escape Markdown v2 special characters
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        
        return text
    
    def _get_grade_emoji(self, score_percentage: float) -> str:
        """Get emoji for score grade."""
        if score_percentage >= 90:
            return "🌟 EXCELLENT"
        elif score_percentage >= 75:
            return "⭐ GREAT"
        elif score_percentage >= 60:
            return "✅ GOOD"
        elif score_percentage >= 45:
            return "⚠️ MARGINAL"
        else:
            return "❌ POOR"
    
    def _get_priority_text(self, score_percentage: float) -> str:
        """Get priority text for score."""
        if score_percentage >= 90:
            return "🔥 HIGH PRIORITY"
        elif score_percentage >= 75:
            return "🚀 RECOMMENDED"
        elif score_percentage >= 60:
            return "👀 WORTH CONSIDERING"
        elif score_percentage >= 45:
            return "🤔 QUESTIONABLE"
        else:
            return "🚫 NOT RECOMMENDED"
    
    def _get_score_emoji(self, percentage: float) -> str:
        """Get emoji for individual score component."""
        if percentage >= 90:
            return "🌟"
        elif percentage >= 75:
            return "⭐"
        elif percentage >= 60:
            return "✅"
        elif percentage >= 45:
            return "⚠️"
        else:
            return "❌"
    
    def _create_job_keyboard(self, job_id: str, preferences: TelegramUserPreferences) -> InlineKeyboardMarkup:
        """Create interactive keyboard for individual job."""
        buttons = []
        
        if preferences.enable_job_actions:
            # First row: Primary actions
            buttons.append([
                InlineKeyboardButton("💾 Save", callback_data=f"save_{job_id}"),
                InlineKeyboardButton("🔗 Apply", callback_data=f"apply_{job_id}"),
                InlineKeyboardButton("❌ Dismiss", callback_data=f"dismiss_{job_id}")
            ])
            
            # Second row: Additional actions
            buttons.append([
                InlineKeyboardButton("📊 Detailed Score", callback_data=f"score_{job_id}"),
                InlineKeyboardButton("🔍 Similar Jobs", callback_data=f"similar_{job_id}")
            ])
        
        return InlineKeyboardMarkup(buttons)
    
    def _create_batch_keyboard(self, job_count: int) -> InlineKeyboardMarkup:
        """Create keyboard for batch job message."""
        buttons = []
        
        # Navigation buttons
        if job_count > 5:
            buttons.append([
                InlineKeyboardButton("📖 View Individual Jobs", callback_data="view_individual"),
                InlineKeyboardButton("🔍 Search Jobs", callback_data="search_jobs")
            ])
        
        # Settings and actions
        buttons.append([
            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            InlineKeyboardButton("📈 My Stats", callback_data="stats")
        ])
        
        return InlineKeyboardMarkup(buttons)


class TelegramUserDatabase:
    """Database manager for Telegram user data and preferences."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = get_logger(__name__)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self._init_database()
    
    def _init_database(self):
        """Initialize user database schema."""
        with self._get_connection() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    preferences_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_active TEXT
                );
                
                CREATE TABLE IF NOT EXISTS job_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    job_id TEXT NOT NULL,
                    message_id INTEGER,
                    delivered_at TEXT NOT NULL,
                    user_action TEXT,
                    action_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_deliveries_user_id ON job_deliveries(user_id);
                CREATE INDEX IF NOT EXISTS idx_deliveries_job_id ON job_deliveries(job_id);
                CREATE INDEX IF NOT EXISTS idx_deliveries_delivered_at ON job_deliveries(delivered_at);
                
                CREATE TABLE IF NOT EXISTS user_saved_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    job_id TEXT NOT NULL,
                    saved_at TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    UNIQUE(user_id, job_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_saved_jobs_user_id ON user_saved_jobs(user_id);
            ''')
    
    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def get_user_preferences(self, user_id: int) -> Optional[TelegramUserPreferences]:
        """Get user preferences."""
        with self._get_connection() as conn:
            row = conn.execute(
                'SELECT preferences_json FROM users WHERE user_id = ?',
                (user_id,)
            ).fetchone()
            
            if row:
                prefs_data = json.loads(row['preferences_json'])
                return TelegramUserPreferences(**prefs_data)
            
            return None
    
    def save_user_preferences(self, preferences: TelegramUserPreferences):
        """Save user preferences."""
        preferences.updated_at = datetime.now()
        
        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO users (user_id, username, preferences_json, created_at, updated_at, last_active)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                preferences.user_id,
                preferences.username,
                json.dumps(asdict(preferences), default=str),
                preferences.created_at.isoformat(),
                preferences.updated_at.isoformat(),
                datetime.now().isoformat()
            ))
            conn.commit()
    
    def record_job_delivery(self, user_id: int, job_id: str, message_id: Optional[int] = None):
        """Record job delivery to user."""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO job_deliveries (user_id, job_id, message_id, delivered_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, job_id, message_id, datetime.now().isoformat()))
            conn.commit()
    
    def record_user_action(self, user_id: int, job_id: str, action: str):
        """Record user action on job."""
        with self._get_connection() as conn:
            conn.execute('''
                UPDATE job_deliveries 
                SET user_action = ?, action_at = ?
                WHERE user_id = ? AND job_id = ? AND user_action IS NULL
            ''', (action, datetime.now().isoformat(), user_id, job_id))
            conn.commit()
    
    def save_job_for_user(self, user_id: int, job_id: str, notes: str = ""):
        """Save job for user."""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO user_saved_jobs (user_id, job_id, saved_at, notes)
                VALUES (?, ?, ?, ?)
            ''', (user_id, job_id, datetime.now().isoformat(), notes))
            conn.commit()
    
    def get_user_saved_jobs(self, user_id: int, limit: int = 20) -> List[str]:
        """Get user's saved job IDs."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT job_id FROM user_saved_jobs 
                WHERE user_id = ? 
                ORDER BY saved_at DESC 
                LIMIT ?
            ''', (user_id, limit)).fetchall()
            
            return [row['job_id'] for row in rows]
    
    def get_all_active_users(self) -> List[int]:
        """Get all users with delivery enabled."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT user_id FROM users 
                WHERE json_extract(preferences_json, '$.enabled') = 1
            ''').fetchall()
            
            return [row['user_id'] for row in rows]
    
    def update_last_active(self, user_id: int):
        """Update user's last active timestamp."""
        with self._get_connection() as conn:
            conn.execute('''
                UPDATE users SET last_active = ? WHERE user_id = ?
            ''', (datetime.now().isoformat(), user_id))
            conn.commit()


class PMJobTelegramBot:
    """
    Main Telegram bot for PM job delivery with interactive features.
    
    Features:
    - Automated job delivery based on user preferences
    - Interactive job management (save, dismiss, apply)
    - User preference configuration via chat commands
    - Job search and filtering capabilities
    - Delivery statistics and insights
    """
    
    def __init__(self, 
                 bot_token: str,
                 job_storage: JobStorage,
                 pm_scorer: DefaultPMScorer,
                 pm_profile: PMProfile,
                 system_settings: SystemSettings,
                 db_path: str = "data/telegram/users.db"):
        """Initialize Telegram bot."""
        self.bot_token = bot_token
        self.job_storage = job_storage
        self.pm_scorer = pm_scorer
        self.pm_profile = pm_profile
        self.system_settings = system_settings
        
        self.logger = get_logger(__name__)
        self.user_db = TelegramUserDatabase(db_path)
        self.message_formatter = TelegramMessageFormatter(pm_scorer)
        
        # Bot application
        self.app = Application.builder().token(bot_token).build()
        self._setup_handlers()
        
        # Delivery scheduling
        self._delivery_tasks = {}
        self._is_running = False
    
    def _setup_handlers(self):
        """Setup bot command and callback handlers."""
        
        # Command handlers
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(CommandHandler("help", self._handle_help))
        self.app.add_handler(CommandHandler("settings", self._handle_settings))
        self.app.add_handler(CommandHandler("search", self._handle_search))
        self.app.add_handler(CommandHandler("saved", self._handle_saved_jobs))
        self.app.add_handler(CommandHandler("stats", self._handle_stats))
        self.app.add_handler(CommandHandler("stop", self._handle_stop))
        
        # Callback handlers for inline buttons
        self.app.add_handler(CallbackQueryHandler(self._handle_job_action, pattern=r"^(save|apply|dismiss)_"))
        self.app.add_handler(CallbackQueryHandler(self._handle_score_request, pattern=r"^score_"))
        self.app.add_handler(CallbackQueryHandler(self._handle_similar_jobs, pattern=r"^similar_"))
        self.app.add_handler(CallbackQueryHandler(self._handle_settings_callback, pattern=r"^settings"))
        self.app.add_handler(CallbackQueryHandler(self._handle_stats_callback, pattern=r"^stats"))
        
        # Message handlers
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        
        # Error handler
        self.app.add_error_handler(self._handle_error)
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        # Create default preferences for new user
        preferences = TelegramUserPreferences(user_id=user_id, username=username)
        self.user_db.save_user_preferences(preferences)
        
        welcome_message = """
🎯 **Welcome to PM Watchman!**

I'll help you discover and track relevant Product Manager jobs based on your preferences.

**What I can do:**
🔍 Find PM jobs from multiple sources (LinkedIn, RSS feeds)
📊 Score jobs based on your profile (skills, experience, preferences)
📱 Deliver personalized job alerts
💾 Help you save and organize interesting opportunities
📈 Track your job search progress

**Getting Started:**
• Use /settings to configure your preferences
• Use /search to find jobs immediately  
• Use /help to see all available commands

**Privacy:** Your data is stored securely and never shared. Use /stop to disable notifications anytime.

Ready to find your next PM role? Use /search to get started! 🚀
        """
        
        await update.message.reply_text(
            welcome_message, 
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
        self.user_db.update_last_active(user_id)
    
    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_message = """
🤖 **PM Watchman Commands**

**Job Discovery:**
/search \\- Find PM jobs matching your profile
/saved \\- View your saved jobs

**Settings & Preferences:**
/settings \\- Configure delivery preferences
/stats \\- View your job search statistics

**Other Commands:**
/help \\- Show this help message
/stop \\- Disable job notifications

**Interactive Features:**
• 💾 Save jobs for later review
• 🔗 Quick apply links
• 📊 Detailed scoring breakdowns
• 🔍 Find similar opportunities

**Tips:**
• Set your minimum score threshold in settings
• Use keywords to filter jobs
• Check stats to see your search progress
• Saved jobs are accessible anytime with /saved

Need more help? The bot learns from your interactions to improve recommendations\\!
        """
        
        await update.message.reply_text(
            help_message,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    async def _handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command."""
        user_id = update.effective_user.id
        self.user_db.update_last_active(user_id)
        
        # Get user preferences
        preferences = self.user_db.get_user_preferences(user_id)
        if not preferences:
            await update.message.reply_text(
                "Please use /start first to set up your preferences\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        
        # Search for recent jobs
        await update.message.reply_text("🔍 Searching for PM jobs\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)
        
        try:
            # Get recent jobs from storage
            recent_jobs = self.job_storage.load_jobs(limit=50, since=datetime.now() - timedelta(days=7))
            
            if not recent_jobs:
                await update.message.reply_text(
                    "No recent jobs found\\. The system may be gathering new opportunities\\.",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                return
            
            # Score and filter jobs
            scored_jobs = await self._score_and_filter_jobs(recent_jobs, preferences)
            
            if not scored_jobs:
                await update.message.reply_text(
                    f"No jobs found matching your criteria \\(minimum score: {preferences.min_score_threshold}%\\)\\. Try adjusting your filters in /settings\\.",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                return
            
            # Send jobs to user
            await self._send_jobs_to_user(user_id, scored_jobs, preferences, context)
            
        except Exception as e:
            self.logger.error(f"Search failed for user {user_id}: {e}")
            await update.message.reply_text(
                "Sorry, there was an error searching for jobs\\. Please try again later\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
    
    async def _handle_job_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle job action button clicks."""
        query = update.callback_query
        user_id = query.from_user.id
        action, job_id = query.data.split('_', 1)
        
        self.user_db.update_last_active(user_id)
        
        if action == "save":
            self.user_db.save_job_for_user(user_id, job_id)
            self.user_db.record_user_action(user_id, job_id, "saved")
            await query.answer("Job saved! 💾")
            
        elif action == "apply":
            # Get job URL and provide apply link
            self.user_db.record_user_action(user_id, job_id, "applied")
            await query.answer("Opening application link... 🔗")
            
        elif action == "dismiss":
            self.user_db.record_user_action(user_id, job_id, "dismissed")
            await query.answer("Job dismissed ❌")
    
    async def _handle_score_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle detailed score request."""
        query = update.callback_query
        job_id = query.data.replace('score_', '')
        
        # TODO: Get job details and show detailed scoring
        await query.answer("Detailed scoring coming soon! 📊")
    
    async def _handle_similar_jobs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle similar jobs request."""
        query = update.callback_query
        job_id = query.data.replace('similar_', '')
        
        # TODO: Find similar jobs based on title, company, skills
        await query.answer("Similar jobs feature coming soon! 🔍")
    
    async def _handle_settings_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle settings callback."""
        await update.callback_query.answer("Settings coming soon! ⚙️")
    
    async def _handle_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle stats callback."""
        await update.callback_query.answer("Statistics coming soon! 📈")
    
    async def _handle_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command."""
        user_id = update.effective_user.id
        preferences = self.user_db.get_user_preferences(user_id)
        
        if not preferences:
            await update.message.reply_text(
                "Please use /start first to initialize your preferences\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        
        settings_message = f"""
⚙️ **Your Current Settings**

**Delivery Preferences:**
• Status: {'✅ Enabled' if preferences.enabled else '❌ Disabled'}
• Frequency: {preferences.frequency}
• Delivery Time: {preferences.delivery_time}
• Max Jobs Per Day: {preferences.max_daily_jobs}

**Filtering:**
• Minimum Score: {preferences.min_score_threshold}%
• Include Description: {'Yes' if preferences.include_description_preview else 'No'}
• Detailed Scoring: {'Yes' if preferences.include_detailed_scoring else 'No'}

**Interaction:**
• Job Actions: {'Enabled' if preferences.enable_job_actions else 'Disabled'}
• Search: {'Enabled' if preferences.enable_search else 'Disabled'}

*Settings configuration UI coming soon\\! For now, contact support to modify settings\\.*
        """
        
        await update.message.reply_text(
            settings_message,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    async def _handle_saved_jobs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /saved command."""
        user_id = update.effective_user.id
        saved_job_ids = self.user_db.get_user_saved_jobs(user_id)
        
        if not saved_job_ids:
            await update.message.reply_text(
                "You haven't saved any jobs yet\\. Use the 💾 Save button on jobs you're interested in\\!",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        
        # TODO: Load full job details and display
        message = f"📁 **Your Saved Jobs ({len(saved_job_ids)} total)**\n\n"
        message += "Feature coming soon\\! Your saved jobs are safely stored\\."
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2)
    
    async def _handle_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command."""
        # TODO: Implement user statistics
        await update.message.reply_text(
            "📈 **Your Job Search Stats**\n\nStatistics feature coming soon\\!",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    async def _handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command."""
        user_id = update.effective_user.id
        
        # Disable notifications for user
        preferences = self.user_db.get_user_preferences(user_id)
        if preferences:
            preferences.enabled = False
            self.user_db.save_user_preferences(preferences)
        
        await update.message.reply_text(
            "❌ Job notifications disabled\\. Use /start to re\\-enable anytime\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle general text messages."""
        # For now, provide helpful response
        await update.message.reply_text(
            "👋 I understand text\\, but I'm designed for specific commands\\!\n\nTry:\n• /search \\- Find jobs\n• /help \\- See all commands",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    async def _handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle bot errors."""
        self.logger.error(f"Telegram bot error: {context.error}", exc_info=True)
    
    async def _score_and_filter_jobs(self, 
                                   jobs: List[JobData], 
                                   preferences: TelegramUserPreferences) -> List[EnrichedJobData]:
        """Score and filter jobs based on user preferences."""
        filtered_jobs = []
        
        for job in jobs:
            # Score job
            try:
                score_result = self.pm_scorer.score_job(job, self.pm_profile, self.system_settings)
                
                # Apply minimum score threshold
                if score_result.total_score < preferences.min_score_threshold:
                    continue
                
                # Apply keyword filters
                if preferences.excluded_keywords:
                    job_text = f"{job.title} {job.company} {getattr(job, 'description', '')}".lower()
                    if any(keyword.lower() in job_text for keyword in preferences.excluded_keywords):
                        continue
                
                if preferences.required_keywords:
                    job_text = f"{job.title} {job.company} {getattr(job, 'description', '')}".lower()
                    if not any(keyword.lower() in job_text for keyword in preferences.required_keywords):
                        continue
                
                # Apply company filters
                if preferences.excluded_companies:
                    if any(company.lower() in job.company.lower() for company in preferences.excluded_companies):
                        continue
                
                # Create enriched job data (minimal for now)
                from processing.job_enricher import EnrichedJobData
                enriched = EnrichedJobData(original_job=job)
                enriched.pm_score = score_result
                
                filtered_jobs.append(enriched)
                
            except Exception as e:
                self.logger.warning(f"Failed to score job {job.id}: {e}")
                continue
        
        # Sort by score (highest first) and limit
        filtered_jobs.sort(key=lambda x: x.pm_score.total_score, reverse=True)
        return filtered_jobs[:preferences.max_daily_jobs]
    
    async def _send_jobs_to_user(self, 
                               user_id: int, 
                               jobs: List[EnrichedJobData],
                               preferences: TelegramUserPreferences,
                               context: ContextTypes.DEFAULT_TYPE):
        """Send jobs to user via Telegram."""
        
        if preferences.max_jobs_per_message == 1:
            # Send individual job messages
            for job in jobs[:5]:  # Limit to 5 to avoid spam
                try:
                    message, keyboard = self.message_formatter.format_job_message(
                        job, preferences, show_detailed_scoring=preferences.include_detailed_scoring
                    )
                    
                    sent_message = await context.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                    
                    # Record delivery
                    self.user_db.record_job_delivery(
                        user_id, 
                        job.original_job.id, 
                        sent_message.message_id
                    )
                    
                except Exception as e:
                    self.logger.error(f"Failed to send job {job.original_job.id} to user {user_id}: {e}")
                    continue
        else:
            # Send batch message
            try:
                message, keyboard = self.message_formatter.format_batch_message(jobs, preferences)
                
                sent_message = await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                
                # Record deliveries for all jobs in batch
                for job in jobs:
                    self.user_db.record_job_delivery(
                        user_id,
                        job.original_job.id,
                        sent_message.message_id
                    )
                    
            except Exception as e:
                self.logger.error(f"Failed to send batch jobs to user {user_id}: {e}")
    
    async def deliver_jobs_to_all_users(self, jobs: List[EnrichedJobData]):
        """Deliver jobs to all active users based on their preferences."""
        active_users = self.user_db.get_all_active_users()
        
        self.logger.info(f"Delivering jobs to {len(active_users)} active users")
        
        for user_id in active_users:
            try:
                preferences = self.user_db.get_user_preferences(user_id)
                if not preferences or not preferences.enabled:
                    continue
                
                # Filter jobs for this user
                user_jobs = await self._score_and_filter_jobs(
                    [job.original_job for job in jobs], 
                    preferences
                )
                
                if user_jobs:
                    # Create context for sending messages
                    context = ContextTypes.DEFAULT_TYPE(self.app)
                    
                    await self._send_jobs_to_user(user_id, user_jobs, preferences, context)
                    
                    self.logger.info(f"Delivered {len(user_jobs)} jobs to user {user_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to deliver jobs to user {user_id}: {e}")
                continue
    
    async def start_bot(self):
        """Start the Telegram bot."""
        self._is_running = True
        self.logger.info("Starting PM Watchman Telegram bot")
        
        await self.app.initialize()
        await self.app.start()
        
        # Start polling for updates
        await self.app.updater.start_polling()
        
        self.logger.info("Telegram bot is running")
    
    async def stop_bot(self):
        """Stop the Telegram bot."""
        self._is_running = False
        self.logger.info("Stopping PM Watchman Telegram bot")
        
        if self.app.updater.running:
            await self.app.updater.stop()
        
        await self.app.stop()
        await self.app.shutdown()
        
        self.logger.info("Telegram bot stopped")
    
    def is_running(self) -> bool:
        """Check if bot is running."""
        return self._is_running