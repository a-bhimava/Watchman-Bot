"""
Job Storage System

Reliable file-based storage system for job data with comprehensive
duplicate detection, data integrity checks, and efficient querying.
"""

import json
import os
import hashlib
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import shutil
import threading
from contextlib import contextmanager
import fcntl

from integrations.rss_processor import JobData
from utils.logger import get_logger, performance_tracker, log_context
from utils.error_handler import DataProcessingError, retry_on_failure


@dataclass
class JobStorageConfig:
    """Configuration for job storage system."""
    storage_directory: str = "data/jobs"
    index_directory: str = "data/indices"
    backup_directory: str = "data/backups"
    max_file_size_mb: int = 10
    max_jobs_per_file: int = 1000
    duplicate_threshold_days: int = 30
    backup_retention_days: int = 7
    enable_compression: bool = True


@dataclass
class StorageStats:
    """Storage system statistics."""
    total_jobs: int = 0
    unique_jobs: int = 0
    duplicates_detected: int = 0
    files_count: int = 0
    total_size_mb: float = 0.0
    oldest_job: Optional[datetime] = None
    newest_job: Optional[datetime] = None
    last_cleanup: Optional[datetime] = None


class JobIndex:
    """
    Efficient job indexing system for fast duplicate detection and querying.
    Uses SQLite for performance with file-based durability.
    """
    
    def __init__(self, index_path: str):
        """Initialize job index."""
        self.index_path = index_path
        self.logger = get_logger(__name__)
        self._lock = threading.RLock()
        
        # Ensure index directory exists
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database schema."""
        with self._get_connection() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    content_hash TEXT UNIQUE,
                    url_hash TEXT,
                    posted_date TEXT,
                    scraped_at TEXT NOT NULL,
                    source TEXT,
                    file_path TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_content_hash ON jobs(content_hash);
                CREATE INDEX IF NOT EXISTS idx_url_hash ON jobs(url_hash);
                CREATE INDEX IF NOT EXISTS idx_company ON jobs(company);
                CREATE INDEX IF NOT EXISTS idx_scraped_at ON jobs(scraped_at);
                CREATE INDEX IF NOT EXISTS idx_source ON jobs(source);
                CREATE INDEX IF NOT EXISTS idx_created_at ON jobs(created_at);
                
                CREATE TABLE IF NOT EXISTS duplicates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_job_id TEXT,
                    duplicate_job_id TEXT,
                    detection_method TEXT,
                    similarity_score REAL,
                    detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (original_job_id) REFERENCES jobs(id),
                    FOREIGN KEY (duplicate_job_id) REFERENCES jobs(id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_duplicates_original ON duplicates(original_job_id);
                CREATE INDEX IF NOT EXISTS idx_duplicates_duplicate ON duplicates(duplicate_job_id);
            ''')
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper locking."""
        with self._lock:
            conn = sqlite3.connect(self.index_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()
    
    def add_job(self, job: JobData, file_path: str) -> bool:
        """
        Add job to index.
        
        Args:
            job: Job data to index
            file_path: Path where job data is stored
            
        Returns:
            True if job was added, False if duplicate detected
        """
        content_hash = self._compute_content_hash(job)
        url_hash = self._compute_url_hash(job.url) if job.url else None
        
        with self._get_connection() as conn:
            # Check for duplicates first
            if self._is_duplicate(conn, content_hash, url_hash):
                self._record_duplicate(conn, job.id, content_hash, url_hash)
                return False
            
            # Insert new job
            conn.execute('''
                INSERT INTO jobs (
                    id, title, company, location, content_hash, url_hash,
                    posted_date, scraped_at, source, file_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job.id,
                job.title,
                job.company,
                job.location,
                content_hash,
                url_hash,
                job.posted_date,
                job.scraped_at.isoformat() if job.scraped_at else None,
                job.source,
                file_path
            ))
            
            conn.commit()
            return True
    
    def _compute_content_hash(self, job: JobData) -> str:
        """Compute content-based hash for duplicate detection."""
        # Normalize content for comparison
        content = f"{job.title.lower().strip()}{job.company.lower().strip()}"
        
        # Add location if available
        if job.location:
            content += job.location.lower().strip()
        
        # Add description if available (first 500 chars to avoid minor differences)
        if hasattr(job, 'description') and job.description:
            content += job.description.lower().strip()[:500]
        
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _compute_url_hash(self, url: str) -> Optional[str]:
        """Compute URL hash for duplicate detection."""
        if not url:
            return None
        
        # Normalize URL (remove tracking parameters, etc.)
        normalized_url = url.lower().split('?')[0]  # Remove query parameters
        return hashlib.md5(normalized_url.encode()).hexdigest()
    
    def _is_duplicate(self, conn, content_hash: str, url_hash: Optional[str]) -> bool:
        """Check if job is a duplicate."""
        # Check content hash
        result = conn.execute(
            'SELECT id FROM jobs WHERE content_hash = ?', (content_hash,)
        ).fetchone()
        
        if result:
            return True
        
        # Check URL hash if available
        if url_hash:
            result = conn.execute(
                'SELECT id FROM jobs WHERE url_hash = ?', (url_hash,)
            ).fetchone()
            
            if result:
                return True
        
        return False
    
    def _record_duplicate(self, conn, job_id: str, content_hash: str, url_hash: Optional[str]):
        """Record duplicate detection."""
        # Find original job
        original = conn.execute(
            'SELECT id FROM jobs WHERE content_hash = ? OR url_hash = ?', 
            (content_hash, url_hash)
        ).fetchone()
        
        if original:
            conn.execute('''
                INSERT INTO duplicates (original_job_id, duplicate_job_id, detection_method)
                VALUES (?, ?, ?)
            ''', (original['id'], job_id, 'hash_match'))
            conn.commit()
    
    def get_job_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        with self._get_connection() as conn:
            # Total jobs
            total_jobs = conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
            
            # Duplicates
            duplicates = conn.execute('SELECT COUNT(*) FROM duplicates').fetchone()[0]
            
            # Date range
            date_range = conn.execute('''
                SELECT MIN(scraped_at), MAX(scraped_at) FROM jobs
            ''').fetchone()
            
            # Source breakdown
            sources = conn.execute('''
                SELECT source, COUNT(*) FROM jobs GROUP BY source
            ''').fetchall()
            
            return {
                'total_jobs': total_jobs,
                'duplicates_detected': duplicates,
                'unique_jobs': total_jobs,  # All indexed jobs are unique
                'oldest_job': date_range[0],
                'newest_job': date_range[1],
                'sources': dict(sources)
            }
    
    def cleanup_old_jobs(self, retention_days: int) -> int:
        """Remove old job entries from index."""
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
        
        with self._get_connection() as conn:
            # Count jobs to be removed
            count = conn.execute(
                'SELECT COUNT(*) FROM jobs WHERE created_at < ?', (cutoff_date,)
            ).fetchone()[0]
            
            # Remove old jobs and their duplicate records
            conn.execute('DELETE FROM duplicates WHERE original_job_id IN (SELECT id FROM jobs WHERE created_at < ?)', (cutoff_date,))
            conn.execute('DELETE FROM duplicates WHERE duplicate_job_id IN (SELECT id FROM jobs WHERE created_at < ?)', (cutoff_date,))
            conn.execute('DELETE FROM jobs WHERE created_at < ?', (cutoff_date,))
            
            conn.commit()
            
            return count


class JobStorage:
    """
    Comprehensive job storage system with file management,
    duplicate detection, and data integrity features.
    """
    
    def __init__(self, config: JobStorageConfig):
        """Initialize job storage system."""
        self.config = config
        self.logger = get_logger(__name__)
        self._lock = threading.RLock()
        
        # Create directories
        for directory in [config.storage_directory, config.index_directory, config.backup_directory]:
            os.makedirs(directory, exist_ok=True)
        
        # Initialize index
        index_path = os.path.join(config.index_directory, "jobs.db")
        self.index = JobIndex(index_path)
        
        # Current storage file
        self.current_file_path = None
        self.current_file_job_count = 0
    
    def _get_current_storage_file(self) -> str:
        """Get current storage file path, creating new one if needed."""
        if (self.current_file_path is None or 
            self.current_file_job_count >= self.config.max_jobs_per_file or
            self._file_size_exceeds_limit(self.current_file_path)):
            
            # Create new storage file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jobs_{timestamp}.jsonl"
            self.current_file_path = os.path.join(self.config.storage_directory, filename)
            self.current_file_job_count = 0
            
            self.logger.info(f"Created new storage file: {self.current_file_path}")
        
        return self.current_file_path
    
    def _file_size_exceeds_limit(self, file_path: Optional[str]) -> bool:
        """Check if file exceeds size limit."""
        if not file_path or not os.path.exists(file_path):
            return False
        
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        return size_mb > self.config.max_file_size_mb
    
    @performance_tracker("job_storage", "store_jobs")
    def store_jobs(self, jobs: List[JobData]) -> Dict[str, Any]:
        """
        Store jobs with duplicate detection.
        
        Args:
            jobs: List of jobs to store
            
        Returns:
            Storage results with statistics
        """
        with self._lock:
            results = {
                'stored_count': 0,
                'duplicate_count': 0,
                'error_count': 0,
                'file_path': None,
                'errors': []
            }
            
            if not jobs:
                return results
            
            with log_context("job_storage", operation="store_jobs", job_count=len(jobs)):
                storage_file = self._get_current_storage_file()
                results['file_path'] = storage_file
                
                # Write jobs to file
                try:
                    with open(storage_file, 'a', encoding='utf-8') as f:
                        # Use file locking to prevent concurrent writes
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        
                        for job in jobs:
                            try:
                                # Check for duplicate
                                if self.index.add_job(job, storage_file):
                                    # Not a duplicate, store job
                                    job_data = asdict(job)
                                    
                                    # Convert datetime objects to strings
                                    for key, value in job_data.items():
                                        if isinstance(value, datetime):
                                            job_data[key] = value.isoformat()
                                    
                                    f.write(json.dumps(job_data) + '\n')
                                    f.flush()  # Ensure data is written
                                    
                                    results['stored_count'] += 1
                                    self.current_file_job_count += 1
                                else:
                                    results['duplicate_count'] += 1
                                    self.logger.debug(f"Duplicate job detected: {job.id}")
                            
                            except Exception as e:
                                results['error_count'] += 1
                                error_msg = f"Failed to store job {job.id}: {e}"
                                results['errors'].append(error_msg)
                                self.logger.error(error_msg)
                
                except Exception as e:
                    error_msg = f"Failed to open storage file: {e}"
                    results['errors'].append(error_msg)
                    self.logger.error(error_msg)
                    raise DataProcessingError(error_msg)
                
                self.logger.info(f"Storage completed", extra={
                    'stored': results['stored_count'],
                    'duplicates': results['duplicate_count'],
                    'errors': results['error_count']
                })
                
                return results
    
    @performance_tracker("job_storage", "load_jobs")
    def load_jobs(self, 
                  limit: Optional[int] = None,
                  source: Optional[str] = None,
                  since: Optional[datetime] = None) -> List[JobData]:
        """
        Load jobs from storage.
        
        Args:
            limit: Maximum number of jobs to load
            source: Filter by job source
            since: Only load jobs scraped after this date
            
        Returns:
            List of JobData objects
        """
        jobs = []
        loaded_count = 0
        
        # Get all storage files
        storage_files = []
        for file_path in Path(self.config.storage_directory).glob("jobs_*.jsonl"):
            storage_files.append(str(file_path))
        
        # Sort by creation time (newest first)
        storage_files.sort(key=lambda x: os.path.getctime(x), reverse=True)
        
        for file_path in storage_files:
            if limit and loaded_count >= limit:
                break
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if limit and loaded_count >= limit:
                            break
                        
                        try:
                            job_data = json.loads(line.strip())
                            
                            # Convert string dates back to datetime
                            if 'scraped_at' in job_data and job_data['scraped_at']:
                                job_data['scraped_at'] = datetime.fromisoformat(job_data['scraped_at'])
                            
                            job = JobData(**job_data)
                            
                            # Apply filters
                            if source and job.source != source:
                                continue
                            
                            if since and job.scraped_at and job.scraped_at < since:
                                continue
                            
                            jobs.append(job)
                            loaded_count += 1
                            
                        except (json.JSONDecodeError, TypeError) as e:
                            self.logger.warning(f"Failed to parse job data in {file_path}: {e}")
                            continue
            
            except Exception as e:
                self.logger.error(f"Failed to read storage file {file_path}: {e}")
                continue
        
        self.logger.info(f"Loaded {len(jobs)} jobs from storage")
        return jobs
    
    def get_storage_stats(self) -> StorageStats:
        """Get comprehensive storage statistics."""
        stats = StorageStats()
        
        # File-level statistics
        storage_files = list(Path(self.config.storage_directory).glob("jobs_*.jsonl"))
        stats.files_count = len(storage_files)
        
        # Calculate total size
        total_size = sum(f.stat().st_size for f in storage_files)
        stats.total_size_mb = total_size / (1024 * 1024)
        
        # Get index statistics
        index_stats = self.index.get_job_stats()
        stats.total_jobs = index_stats['total_jobs']
        stats.unique_jobs = index_stats['unique_jobs']
        stats.duplicates_detected = index_stats['duplicates_detected']
        
        # Parse date range
        if index_stats['oldest_job']:
            stats.oldest_job = datetime.fromisoformat(index_stats['oldest_job'])
        if index_stats['newest_job']:
            stats.newest_job = datetime.fromisoformat(index_stats['newest_job'])
        
        return stats
    
    @retry_on_failure(max_attempts=2, base_delay=1)
    def create_backup(self) -> str:
        """Create backup of storage directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        backup_path = os.path.join(self.config.backup_directory, backup_name)
        
        try:
            # Copy storage directory
            shutil.copytree(self.config.storage_directory, 
                          os.path.join(backup_path, "jobs"))
            
            # Copy index
            shutil.copytree(self.config.index_directory,
                          os.path.join(backup_path, "indices"))
            
            # Create backup metadata
            metadata = {
                'created_at': datetime.now().isoformat(),
                'stats': asdict(self.get_storage_stats())
            }
            
            with open(os.path.join(backup_path, "metadata.json"), 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info(f"Created backup: {backup_path}")
            return backup_path
            
        except Exception as e:
            self.logger.error(f"Backup creation failed: {e}")
            raise DataProcessingError(f"Backup failed: {e}")
    
    def cleanup_old_backups(self) -> int:
        """Remove old backups based on retention policy."""
        cutoff_date = datetime.now() - timedelta(days=self.config.backup_retention_days)
        removed_count = 0
        
        for backup_path in Path(self.config.backup_directory).glob("backup_*"):
            try:
                # Parse timestamp from backup name
                timestamp_str = backup_path.name.replace("backup_", "")
                backup_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                
                if backup_date < cutoff_date:
                    shutil.rmtree(backup_path)
                    removed_count += 1
                    self.logger.info(f"Removed old backup: {backup_path}")
            
            except Exception as e:
                self.logger.warning(f"Failed to process backup {backup_path}: {e}")
        
        return removed_count
    
    def cleanup_old_jobs(self) -> Dict[str, int]:
        """Clean up old jobs from storage and index."""
        with log_context(operation="cleanup_old_jobs"):
            # Clean up index
            index_removed = self.index.cleanup_old_jobs(self.config.duplicate_threshold_days)
            
            # Clean up old storage files
            cutoff_date = datetime.now() - timedelta(days=self.config.duplicate_threshold_days)
            files_removed = 0
            
            for file_path in Path(self.config.storage_directory).glob("jobs_*.jsonl"):
                try:
                    file_date = datetime.fromtimestamp(file_path.stat().st_ctime)
                    if file_date < cutoff_date:
                        file_path.unlink()
                        files_removed += 1
                        self.logger.info(f"Removed old storage file: {file_path}")
                
                except Exception as e:
                    self.logger.warning(f"Failed to remove old file {file_path}: {e}")
            
            # Clean up old backups
            backups_removed = self.cleanup_old_backups()
            
            cleanup_stats = {
                'index_jobs_removed': index_removed,
                'storage_files_removed': files_removed,
                'backups_removed': backups_removed
            }
            
            self.logger.info("Cleanup completed", extra=cleanup_stats)
            return cleanup_stats


def create_default_storage_config(base_directory: str = "data") -> JobStorageConfig:
    """Create default storage configuration."""
    return JobStorageConfig(
        storage_directory=os.path.join(base_directory, "jobs"),
        index_directory=os.path.join(base_directory, "indices"),
        backup_directory=os.path.join(base_directory, "backups"),
        max_file_size_mb=10,
        max_jobs_per_file=1000,
        duplicate_threshold_days=30,
        backup_retention_days=7,
        enable_compression=True
    )