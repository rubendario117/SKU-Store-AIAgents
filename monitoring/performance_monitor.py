#!/usr/bin/env python3
"""
Performance monitoring and metrics collection system for DPerformance Agent
Tracks system performance, success rates, and provides detailed analytics
"""

import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import threading
from collections import defaultdict, deque

@dataclass
class MetricPoint:
    """Individual metric data point"""
    timestamp: float
    agent: str
    operation: str
    duration: float
    success: bool
    metadata: Dict[str, Any]

@dataclass
class PerformanceStats:
    """Performance statistics for a specific operation"""
    total_operations: int
    successful_operations: int
    failed_operations: int
    average_duration: float
    min_duration: float
    max_duration: float
    success_rate: float
    last_24h_operations: int
    last_24h_success_rate: float

class PerformanceMonitor:
    """Central performance monitoring system"""
    
    def __init__(self, max_history_points=10000):
        self.max_history_points = max_history_points
        self.metrics_history = deque(maxlen=max_history_points)
        self.active_operations = {}  # Track ongoing operations
        self.lock = threading.Lock()
        
        # Performance thresholds
        self.performance_thresholds = {
            'image_sourcing': {
                'max_duration': 60.0,  # 60 seconds
                'min_success_rate': 0.7  # 70%
            },
            'vehicle_applications': {
                'max_duration': 30.0,  # 30 seconds
                'min_success_rate': 0.8  # 80%
            },
            'bigcommerce_upload': {
                'max_duration': 45.0,  # 45 seconds
                'min_success_rate': 0.95  # 95%
            },
            'translation': {
                'max_duration': 10.0,  # 10 seconds
                'min_success_rate': 0.98  # 98%
            }
        }
    
    def start_operation(self, agent: str, operation: str, metadata: Dict[str, Any] = None) -> str:
        """Start monitoring an operation and return operation ID"""
        operation_id = f"{agent}_{operation}_{time.time()}_{id(threading.current_thread())}"
        
        with self.lock:
            self.active_operations[operation_id] = {
                'agent': agent,
                'operation': operation,
                'start_time': time.time(),
                'metadata': metadata or {}
            }
        
        return operation_id
    
    def end_operation(self, operation_id: str, success: bool, metadata: Dict[str, Any] = None):
        """End monitoring an operation and record metrics"""
        with self.lock:
            if operation_id not in self.active_operations:
                return
            
            op_data = self.active_operations.pop(operation_id)
            end_time = time.time()
            duration = end_time - op_data['start_time']
            
            # Merge metadata
            final_metadata = op_data['metadata'].copy()
            if metadata:
                final_metadata.update(metadata)
            
            # Create metric point
            metric = MetricPoint(
                timestamp=end_time,
                agent=op_data['agent'],
                operation=op_data['operation'],
                duration=duration,
                success=success,
                metadata=final_metadata
            )
            
            self.metrics_history.append(metric)
            
            # Check for performance alerts
            self._check_performance_alert(metric)
    
    def record_instant_metric(self, agent: str, operation: str, success: bool, 
                            duration: float, metadata: Dict[str, Any] = None):
        """Record a metric without tracking start/end"""
        metric = MetricPoint(
            timestamp=time.time(),
            agent=agent,
            operation=operation,
            duration=duration,
            success=success,
            metadata=metadata or {}
        )
        
        with self.lock:
            self.metrics_history.append(metric)
            self._check_performance_alert(metric)
    
    def get_performance_stats(self, agent: str = None, operation: str = None, 
                            hours: int = 24) -> Dict[str, PerformanceStats]:
        """Get performance statistics for specified criteria"""
        cutoff_time = time.time() - (hours * 3600)
        
        with self.lock:
            # Filter metrics
            filtered_metrics = []
            for metric in self.metrics_history:
                if metric.timestamp >= cutoff_time:
                    if agent and metric.agent != agent:
                        continue
                    if operation and metric.operation != operation:
                        continue
                    filtered_metrics.append(metric)
        
        # Group by agent_operation
        grouped_metrics = defaultdict(list)
        for metric in filtered_metrics:
            key = f"{metric.agent}_{metric.operation}"
            grouped_metrics[key].append(metric)
        
        # Calculate stats
        stats = {}
        for key, metrics in grouped_metrics.items():
            if not metrics:
                continue
                
            total_ops = len(metrics)
            successful_ops = sum(1 for m in metrics if m.success)
            failed_ops = total_ops - successful_ops
            durations = [m.duration for m in metrics]
            
            # Last 24h stats
            last_24h_cutoff = time.time() - (24 * 3600)
            last_24h_metrics = [m for m in metrics if m.timestamp >= last_24h_cutoff]
            last_24h_ops = len(last_24h_metrics)
            last_24h_successful = sum(1 for m in last_24h_metrics if m.success)
            last_24h_success_rate = last_24h_successful / last_24h_ops if last_24h_ops > 0 else 0
            
            stats[key] = PerformanceStats(
                total_operations=total_ops,
                successful_operations=successful_ops,
                failed_operations=failed_ops,
                average_duration=sum(durations) / len(durations),
                min_duration=min(durations),
                max_duration=max(durations),
                success_rate=successful_ops / total_ops,
                last_24h_operations=last_24h_ops,
                last_24h_success_rate=last_24h_success_rate
            )
        
        return stats
    
    def get_recent_failures(self, hours: int = 24, limit: int = 50) -> List[MetricPoint]:
        """Get recent failed operations"""
        cutoff_time = time.time() - (hours * 3600)
        
        with self.lock:
            failures = []
            for metric in reversed(self.metrics_history):
                if metric.timestamp < cutoff_time:
                    break
                if not metric.success:
                    failures.append(metric)
                if len(failures) >= limit:
                    break
        
        return failures
    
    def export_metrics(self, filepath: str, hours: int = 24):
        """Export metrics to JSON file"""
        cutoff_time = time.time() - (hours * 3600)
        
        with self.lock:
            filtered_metrics = [
                asdict(metric) for metric in self.metrics_history
                if metric.timestamp >= cutoff_time
            ]
        
        export_data = {
            'export_time': datetime.now().isoformat(),
            'time_range_hours': hours,
            'total_metrics': len(filtered_metrics),
            'metrics': filtered_metrics
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
    
    def _check_performance_alert(self, metric: MetricPoint):
        """Check if metric triggers performance alert"""
        operation_key = f"{metric.agent}_{metric.operation}".lower()
        
        # Find matching threshold
        threshold_key = None
        for key in self.performance_thresholds:
            if key in operation_key:
                threshold_key = key
                break
        
        if not threshold_key:
            return
        
        thresholds = self.performance_thresholds[threshold_key]
        alerts = []
        
        # Duration alert
        if metric.duration > thresholds['max_duration']:
            alerts.append(f"Duration {metric.duration:.2f}s exceeds threshold {thresholds['max_duration']}s")
        
        # Success rate alert (check last 10 operations)
        recent_ops = []
        with self.lock:
            for m in reversed(self.metrics_history):
                if m.agent == metric.agent and m.operation == metric.operation:
                    recent_ops.append(m)
                    if len(recent_ops) >= 10:
                        break
        
        if len(recent_ops) >= 5:  # Only check if we have enough data
            recent_success_rate = sum(1 for m in recent_ops if m.success) / len(recent_ops)
            if recent_success_rate < thresholds['min_success_rate']:
                alerts.append(f"Success rate {recent_success_rate:.2%} below threshold {thresholds['min_success_rate']:.2%}")
        
        # Log alerts
        for alert in alerts:
            print(f"⚠️  PERFORMANCE ALERT [{metric.agent}:{metric.operation}]: {alert}")

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

class OperationTimer:
    """Context manager for timing operations"""
    
    def __init__(self, agent: str, operation: str, metadata: Dict[str, Any] = None):
        self.agent = agent
        self.operation = operation
        self.metadata = metadata or {}
        self.operation_id = None
        self.success = False
    
    def __enter__(self):
        self.operation_id = performance_monitor.start_operation(
            self.agent, self.operation, self.metadata
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.success = exc_type is None
        end_metadata = self.metadata.copy()
        if exc_val:
            end_metadata['error'] = str(exc_val)
        performance_monitor.end_operation(
            self.operation_id, 
            self.success,
            end_metadata
        )
    
    def set_metadata(self, key: str, value: Any):
        """Add metadata during operation"""
        self.metadata[key] = value
    
    def mark_success(self):
        """Mark operation as successful"""
        self.success = True
    
    def mark_failure(self):
        """Mark operation as failed"""
        self.success = False

def monitor_operation(agent: str, operation: str, metadata: Dict[str, Any] = None):
    """Decorator for monitoring function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with OperationTimer(agent, operation, metadata) as timer:
                try:
                    result = func(*args, **kwargs)
                    timer.mark_success()
                    return result
                except Exception as e:
                    timer.mark_failure()
                    timer.set_metadata('error', str(e))
                    raise
        return wrapper
    return decorator