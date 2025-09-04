"""
System Health Monitoring and Alerting

Comprehensive monitoring system for job discovery pipeline health,
performance metrics, and automated alerting for issues.
"""

import json
import os
import threading
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import psutil
import sqlite3
from contextlib import contextmanager

from utils.logger import get_logger, performance_tracker
from utils.error_handler import DataProcessingError


class HealthStatus(Enum):
    """System health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # System resources
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    disk_usage_percent: float = 0.0
    
    # Application metrics
    jobs_discovered_last_hour: int = 0
    jobs_stored_last_hour: int = 0
    duplicates_detected_last_hour: int = 0
    avg_job_quality_score: float = 0.0
    
    # Error rates
    error_rate_last_hour: float = 0.0
    warning_rate_last_hour: float = 0.0
    
    # Performance metrics
    avg_discovery_duration_seconds: float = 0.0
    avg_enrichment_duration_seconds: float = 0.0
    avg_storage_duration_seconds: float = 0.0
    
    # Data freshness
    last_successful_discovery: Optional[datetime] = None
    last_linkedin_scrape: Optional[datetime] = None
    last_rss_update: Optional[datetime] = None
    
    # Storage metrics
    total_jobs_stored: int = 0
    storage_size_mb: float = 0.0
    oldest_job_age_days: float = 0.0


@dataclass
class HealthCheck:
    """Individual health check definition."""
    name: str
    description: str
    check_function: Callable[[], bool]
    severity: HealthStatus = HealthStatus.WARNING
    threshold_values: Dict[str, float] = field(default_factory=dict)
    last_check_time: Optional[datetime] = None
    last_status: HealthStatus = HealthStatus.UNKNOWN
    consecutive_failures: int = 0
    max_consecutive_failures: int = 3


@dataclass
class Alert:
    """System alert definition."""
    id: str
    timestamp: datetime
    severity: HealthStatus
    component: str
    message: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class MetricsCollector:
    """Collects system and application metrics."""
    
    def __init__(self, storage_directory: str = "data"):
        self.storage_directory = storage_directory
        self.logger = get_logger(__name__)
        
        # Metrics database
        self.metrics_db_path = os.path.join(storage_directory, "monitoring", "metrics.db")
        os.makedirs(os.path.dirname(self.metrics_db_path), exist_ok=True)
        self._init_metrics_database()
    
    def _init_metrics_database(self):
        """Initialize metrics storage database."""
        with self._get_connection() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON system_metrics(timestamp);
                
                CREATE TABLE IF NOT EXISTS discovery_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT UNIQUE NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    success BOOLEAN NOT NULL,
                    jobs_found INTEGER DEFAULT 0,
                    jobs_stored INTEGER DEFAULT 0,
                    errors_count INTEGER DEFAULT 0,
                    duration_seconds REAL DEFAULT 0,
                    metrics_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_runs_started_at ON discovery_runs(started_at);
                
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    component TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metrics_json TEXT,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);
                CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved);
            ''')
    
    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.metrics_db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    @performance_tracker("metrics_collector", "collect_metrics")
    def collect_current_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        metrics = SystemMetrics()
        
        try:
            # System resources
            metrics.cpu_usage_percent = psutil.cpu_percent(interval=1)
            metrics.memory_usage_percent = psutil.virtual_memory().percent
            
            # Disk usage for data directory
            if os.path.exists(self.storage_directory):
                disk_usage = psutil.disk_usage(self.storage_directory)
                metrics.disk_usage_percent = (disk_usage.used / disk_usage.total) * 100
            
            # Application metrics from database
            self._collect_application_metrics(metrics)
            
        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")
        
        return metrics
    
    def _collect_application_metrics(self, metrics: SystemMetrics):
        """Collect application-specific metrics."""
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        
        with self._get_connection() as conn:
            # Jobs discovered/stored in last hour
            run_stats = conn.execute('''
                SELECT 
                    SUM(jobs_found) as total_found,
                    SUM(jobs_stored) as total_stored,
                    AVG(duration_seconds) as avg_duration,
                    COUNT(*) as run_count
                FROM discovery_runs 
                WHERE started_at >= ?
            ''', (one_hour_ago,)).fetchone()
            
            if run_stats:
                metrics.jobs_discovered_last_hour = run_stats['total_found'] or 0
                metrics.jobs_stored_last_hour = run_stats['total_stored'] or 0
                metrics.avg_discovery_duration_seconds = run_stats['avg_duration'] or 0
            
            # Last successful discovery
            last_success = conn.execute('''
                SELECT started_at FROM discovery_runs 
                WHERE success = 1 
                ORDER BY started_at DESC LIMIT 1
            ''').fetchone()
            
            if last_success:
                metrics.last_successful_discovery = datetime.fromisoformat(last_success['started_at'])
            
            # Storage metrics (approximate from job storage if available)
            try:
                from storage.job_storage import JobStorage, create_default_storage_config
                storage = JobStorage(create_default_storage_config(self.storage_directory))
                storage_stats = storage.get_storage_stats()
                
                metrics.total_jobs_stored = storage_stats.total_jobs
                metrics.storage_size_mb = storage_stats.total_size_mb
                
                if storage_stats.oldest_job:
                    age = datetime.now() - storage_stats.oldest_job
                    metrics.oldest_job_age_days = age.days
                    
            except Exception as e:
                self.logger.debug(f"Could not collect storage metrics: {e}")
    
    def store_metrics(self, metrics: SystemMetrics):
        """Store metrics in database."""
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT INTO system_metrics (timestamp, metrics_json)
                    VALUES (?, ?)
                ''', (
                    metrics.timestamp.isoformat(),
                    json.dumps(asdict(metrics), default=str)
                ))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to store metrics: {e}")
    
    def record_discovery_run(self, run_results: Any):
        """Record discovery run results."""
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO discovery_runs (
                        run_id, started_at, completed_at, success, 
                        jobs_found, jobs_stored, errors_count, duration_seconds, metrics_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    run_results.run_id,
                    run_results.started_at.isoformat(),
                    run_results.completed_at.isoformat() if run_results.completed_at else None,
                    run_results.success,
                    run_results.total_raw_jobs,
                    run_results.jobs_stored,
                    len(run_results.errors),
                    run_results.total_duration_seconds,
                    json.dumps(asdict(run_results), default=str)
                ))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to record discovery run: {e}")
    
    def get_metrics_history(self, hours: int = 24) -> List[SystemMetrics]:
        """Get metrics history for specified time period."""
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        metrics_list = []
        
        try:
            with self._get_connection() as conn:
                rows = conn.execute('''
                    SELECT metrics_json FROM system_metrics 
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                ''', (since,)).fetchall()
                
                for row in rows:
                    metrics_data = json.loads(row['metrics_json'])
                    metrics = SystemMetrics(**metrics_data)
                    metrics_list.append(metrics)
                    
        except Exception as e:
            self.logger.error(f"Failed to get metrics history: {e}")
        
        return metrics_list


class HealthMonitor:
    """
    Comprehensive system health monitoring with configurable checks and alerting.
    """
    
    def __init__(self, 
                 storage_directory: str = "data",
                 check_interval_seconds: int = 300,
                 alert_handlers: List[Callable[[Alert], None]] = None):
        """Initialize health monitor."""
        self.storage_directory = storage_directory
        self.check_interval_seconds = check_interval_seconds
        self.alert_handlers = alert_handlers or []
        
        self.logger = get_logger(__name__)
        self.metrics_collector = MetricsCollector(storage_directory)
        
        # Health checks
        self.health_checks: Dict[str, HealthCheck] = {}
        self.active_alerts: Dict[str, Alert] = {}
        
        # Monitoring state
        self.is_monitoring = False
        self.monitor_thread = None
        self._stop_event = threading.Event()
        
        self._setup_default_health_checks()
    
    def _setup_default_health_checks(self):
        """Setup default health checks."""
        # System resource checks
        self.add_health_check(HealthCheck(
            name="cpu_usage",
            description="CPU usage percentage",
            check_function=lambda: self._check_cpu_usage(),
            severity=HealthStatus.WARNING,
            threshold_values={"warning": 80.0, "critical": 95.0}
        ))
        
        self.add_health_check(HealthCheck(
            name="memory_usage",
            description="Memory usage percentage",
            check_function=lambda: self._check_memory_usage(),
            severity=HealthStatus.WARNING,
            threshold_values={"warning": 80.0, "critical": 95.0}
        ))
        
        self.add_health_check(HealthCheck(
            name="disk_space",
            description="Disk space usage",
            check_function=lambda: self._check_disk_space(),
            severity=HealthStatus.CRITICAL,
            threshold_values={"warning": 85.0, "critical": 95.0}
        ))
        
        # Application health checks
        self.add_health_check(HealthCheck(
            name="recent_discovery",
            description="Recent successful job discovery",
            check_function=lambda: self._check_recent_discovery(),
            severity=HealthStatus.WARNING,
            threshold_values={"max_hours_since_discovery": 8.0}
        ))
        
        self.add_health_check(HealthCheck(
            name="job_quality",
            description="Average job quality score",
            check_function=lambda: self._check_job_quality(),
            severity=HealthStatus.WARNING,
            threshold_values={"min_quality_score": 50.0}
        ))
        
        self.add_health_check(HealthCheck(
            name="error_rate",
            description="Error rate in recent operations",
            check_function=lambda: self._check_error_rate(),
            severity=HealthStatus.WARNING,
            threshold_values={"max_error_rate": 0.1}  # 10%
        ))
    
    def add_health_check(self, health_check: HealthCheck):
        """Add a health check to the monitor."""
        self.health_checks[health_check.name] = health_check
        self.logger.debug(f"Added health check: {health_check.name}")
    
    def remove_health_check(self, name: str) -> bool:
        """Remove a health check."""
        if name in self.health_checks:
            del self.health_checks[name]
            self.logger.debug(f"Removed health check: {name}")
            return True
        return False
    
    def start_monitoring(self):
        """Start continuous health monitoring."""
        if self.is_monitoring:
            self.logger.warning("Health monitoring is already running")
            return
        
        self.is_monitoring = True
        self._stop_event.clear()
        
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="HealthMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        self.logger.info(f"Health monitoring started (interval: {self.check_interval_seconds}s)")
    
    def stop_monitoring(self):
        """Stop health monitoring."""
        if not self.is_monitoring:
            return
        
        self._stop_event.set()
        self.is_monitoring = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        self.logger.info("Health monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while not self._stop_event.is_set():
            try:
                # Collect current metrics
                metrics = self.metrics_collector.collect_current_metrics()
                self.metrics_collector.store_metrics(metrics)
                
                # Run health checks
                self._run_health_checks(metrics)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}", exc_info=True)
            
            # Wait for next interval
            self._stop_event.wait(self.check_interval_seconds)
    
    def _run_health_checks(self, metrics: SystemMetrics):
        """Run all configured health checks."""
        for name, health_check in self.health_checks.items():
            try:
                is_healthy = health_check.check_function()
                health_check.last_check_time = datetime.now()
                
                if is_healthy:
                    health_check.last_status = HealthStatus.HEALTHY
                    health_check.consecutive_failures = 0
                    
                    # Resolve alert if one exists
                    self._resolve_alert(name)
                    
                else:
                    health_check.consecutive_failures += 1
                    
                    if health_check.consecutive_failures >= health_check.max_consecutive_failures:
                        health_check.last_status = health_check.severity
                        self._trigger_alert(name, health_check, metrics)
                    else:
                        health_check.last_status = HealthStatus.WARNING
                        
            except Exception as e:
                self.logger.error(f"Health check {name} failed: {e}")
                health_check.last_status = HealthStatus.UNKNOWN
    
    def _trigger_alert(self, check_name: str, health_check: HealthCheck, metrics: SystemMetrics):
        """Trigger an alert for a failed health check."""
        alert_id = f"{check_name}_{int(time.time())}"
        
        alert = Alert(
            id=alert_id,
            timestamp=datetime.now(),
            severity=health_check.severity,
            component=check_name,
            message=f"Health check '{health_check.description}' failed",
            metrics=asdict(metrics)
        )
        
        self.active_alerts[check_name] = alert
        
        # Store alert in database
        try:
            with self.metrics_collector._get_connection() as conn:
                conn.execute('''
                    INSERT INTO alerts (alert_id, timestamp, severity, component, message, metrics_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    alert.id,
                    alert.timestamp.isoformat(),
                    alert.severity.value,
                    alert.component,
                    alert.message,
                    json.dumps(alert.metrics, default=str)
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to store alert: {e}")
        
        # Notify alert handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                self.logger.error(f"Alert handler failed: {e}")
        
        self.logger.warning(f"Alert triggered: {alert.message}", extra={
            'alert_id': alert.id,
            'severity': alert.severity.value,
            'component': alert.component
        })
    
    def _resolve_alert(self, check_name: str):
        """Resolve an active alert."""
        if check_name in self.active_alerts:
            alert = self.active_alerts[check_name]
            alert.resolved = True
            alert.resolved_at = datetime.now()
            
            # Update database
            try:
                with self.metrics_collector._get_connection() as conn:
                    conn.execute('''
                        UPDATE alerts SET resolved = TRUE, resolved_at = ?
                        WHERE alert_id = ?
                    ''', (alert.resolved_at.isoformat(), alert.id))
                    conn.commit()
            except Exception as e:
                self.logger.error(f"Failed to update resolved alert: {e}")
            
            del self.active_alerts[check_name]
            
            self.logger.info(f"Alert resolved: {check_name}")
    
    # Health check implementations
    def _check_cpu_usage(self) -> bool:
        """Check CPU usage."""
        cpu_percent = psutil.cpu_percent(interval=1)
        thresholds = self.health_checks["cpu_usage"].threshold_values
        return cpu_percent < thresholds.get("warning", 80.0)
    
    def _check_memory_usage(self) -> bool:
        """Check memory usage."""
        memory_percent = psutil.virtual_memory().percent
        thresholds = self.health_checks["memory_usage"].threshold_values
        return memory_percent < thresholds.get("warning", 80.0)
    
    def _check_disk_space(self) -> bool:
        """Check disk space usage."""
        if not os.path.exists(self.storage_directory):
            return True
        
        disk_usage = psutil.disk_usage(self.storage_directory)
        disk_percent = (disk_usage.used / disk_usage.total) * 100
        thresholds = self.health_checks["disk_space"].threshold_values
        return disk_percent < thresholds.get("warning", 85.0)
    
    def _check_recent_discovery(self) -> bool:
        """Check if there has been a recent successful discovery."""
        try:
            with self.metrics_collector._get_connection() as conn:
                last_success = conn.execute('''
                    SELECT started_at FROM discovery_runs 
                    WHERE success = 1 
                    ORDER BY started_at DESC LIMIT 1
                ''').fetchone()
                
                if not last_success:
                    return False
                
                last_time = datetime.fromisoformat(last_success['started_at'])
                hours_since = (datetime.now() - last_time).total_seconds() / 3600
                
                max_hours = self.health_checks["recent_discovery"].threshold_values.get("max_hours_since_discovery", 8.0)
                return hours_since < max_hours
                
        except Exception as e:
            self.logger.error(f"Failed to check recent discovery: {e}")
            return False
    
    def _check_job_quality(self) -> bool:
        """Check average job quality score."""
        try:
            metrics = self.metrics_collector.collect_current_metrics()
            min_quality = self.health_checks["job_quality"].threshold_values.get("min_quality_score", 50.0)
            return metrics.avg_job_quality_score >= min_quality
        except Exception as e:
            self.logger.error(f"Failed to check job quality: {e}")
            return True  # Don't trigger alert on check failure
    
    def _check_error_rate(self) -> bool:
        """Check error rate in recent operations."""
        try:
            one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
            
            with self.metrics_collector._get_connection() as conn:
                stats = conn.execute('''
                    SELECT 
                        COUNT(*) as total_runs,
                        SUM(CASE WHEN errors_count > 0 THEN 1 ELSE 0 END) as error_runs
                    FROM discovery_runs 
                    WHERE started_at >= ?
                ''', (one_hour_ago,)).fetchone()
                
                if not stats or stats['total_runs'] == 0:
                    return True
                
                error_rate = stats['error_runs'] / stats['total_runs']
                max_error_rate = self.health_checks["error_rate"].threshold_values.get("max_error_rate", 0.1)
                
                return error_rate <= max_error_rate
                
        except Exception as e:
            self.logger.error(f"Failed to check error rate: {e}")
            return True
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current system health status."""
        overall_status = HealthStatus.HEALTHY
        check_statuses = {}
        
        for name, check in self.health_checks.items():
            check_statuses[name] = {
                'status': check.last_status.value,
                'last_check': check.last_check_time.isoformat() if check.last_check_time else None,
                'consecutive_failures': check.consecutive_failures,
                'description': check.description
            }
            
            # Determine overall status
            if check.last_status == HealthStatus.CRITICAL:
                overall_status = HealthStatus.CRITICAL
            elif check.last_status == HealthStatus.WARNING and overall_status != HealthStatus.CRITICAL:
                overall_status = HealthStatus.WARNING
        
        return {
            'overall_status': overall_status.value,
            'timestamp': datetime.now().isoformat(),
            'active_alerts': len(self.active_alerts),
            'checks': check_statuses,
            'is_monitoring': self.is_monitoring
        }
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        alerts = []
        
        try:
            with self.metrics_collector._get_connection() as conn:
                rows = conn.execute('''
                    SELECT * FROM alerts 
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                ''', (since,)).fetchall()
                
                for row in rows:
                    alerts.append(dict(row))
                    
        except Exception as e:
            self.logger.error(f"Failed to get recent alerts: {e}")
        
        return alerts


def create_email_alert_handler(smtp_config: Dict[str, Any]) -> Callable[[Alert], None]:
    """Create email alert handler (placeholder for future implementation)."""
    def send_email_alert(alert: Alert):
        # Implement email sending logic here
        print(f"Email alert: {alert.message}")
    
    return send_email_alert


def create_webhook_alert_handler(webhook_url: str) -> Callable[[Alert], None]:
    """Create webhook alert handler."""
    import requests
    
    def send_webhook_alert(alert: Alert):
        try:
            payload = {
                'alert_id': alert.id,
                'timestamp': alert.timestamp.isoformat(),
                'severity': alert.severity.value,
                'component': alert.component,
                'message': alert.message
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            print(f"Webhook alert failed: {e}")
    
    return send_webhook_alert