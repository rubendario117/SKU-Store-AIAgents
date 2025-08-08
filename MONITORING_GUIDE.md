# 📊 DPerformance Agent - Monitoring & Analytics Guide

## Overview

The DPerformance Agent now includes a comprehensive monitoring and analytics system that provides real-time insights into system performance, success rates, and operational health.

## 🚀 Quick Start

### Running the Monitoring Dashboard

```bash
# Start the monitoring dashboard
streamlit run monitoring/dashboard.py
```

The dashboard will be available at `http://localhost:8501`

### Running the Main Application with Monitoring

```bash
# CLI batch processing (with monitoring)
python main.py

# Web UI interface (with monitoring)
streamlit run ui.py
```

## 📈 Dashboard Features

### 1. System Overview
- **Real-time metrics** for last 24 hours
- **Overall success rate** across all operations
- **Average operation duration** 
- **Active operations** currently running
- **Key performance indicators** with delta comparisons

### 2. Agent Performance Breakdown
- **Success rates by agent** (Image, Vehicle Applications, BigCommerce)
- **Operation duration analysis** by agent and operation type
- **Detailed performance table** with filterable metrics
- **Visual charts** showing performance trends

### 3. Failure Analysis
- **Recent failures** with detailed error information
- **Failure distribution** by agent and operation type  
- **Timeline visualization** of failures over time
- **Error categorization** and frequency analysis

### 4. Performance Trends
- **Historical performance data** over different time periods (1h, 6h, 24h, 1 week)
- **Success rate trends** over time
- **Operation volume analysis** 
- **Performance degradation detection**

### 5. Log Analysis
- **Live log file viewer** with syntax highlighting
- **Log file size and modification tracking**
- **Search and filter capabilities**
- **Multiple log format support** (structured JSON, plain text)

### 6. Metrics Export
- **Export performance data** to JSON format
- **Configurable time ranges** for exports
- **Downloadable reports** for offline analysis
- **Integration-ready data formats**

## 🔧 Configuration

### Performance Thresholds

The system monitors against predefined performance thresholds:

```python
# agents/monitoring/performance_monitor.py
performance_thresholds = {
    'image_sourcing': {
        'max_duration': 60.0,     # 60 seconds
        'min_success_rate': 0.7   # 70%
    },
    'vehicle_applications': {
        'max_duration': 30.0,     # 30 seconds
        'min_success_rate': 0.8   # 80%
    },
    'bigcommerce_upload': {
        'max_duration': 45.0,     # 45 seconds
        'min_success_rate': 0.95  # 95%
    }
}
```

### Logging Configuration

Structured logging with multiple output formats:

- **Console logging** with color-coded levels
- **File logging** with rotation (10MB files, 5 backups)
- **JSON structured logs** for programmatic analysis
- **Error-specific logs** for critical issues

## 📊 Key Metrics Tracked

### Operation Metrics
- **Duration** - Time taken for each operation
- **Success/Failure rates** - Operation outcome tracking
- **Throughput** - Operations per minute/hour
- **Error categorization** - Types and frequency of errors

### Agent-Specific Metrics
- **Image Sourcing**: Search success rate, image quality scores, source diversity
- **Vehicle Applications**: Parsing success rate, official vs fallback data usage
- **BigCommerce Upload**: Product creation rate, image upload success, API response times

### System Health Metrics
- **Memory usage** during batch processing
- **Concurrent operation handling**
- **Cache hit/miss rates**
- **API rate limiting compliance**

## 🚨 Alerting & Notifications

### Performance Alerts
- **Duration threshold exceeded** - Operations taking longer than expected
- **Success rate below threshold** - When agent performance degrades
- **Error spike detection** - Sudden increase in failure rates
- **Resource utilization warnings** - High memory or CPU usage

### Alert Channels
- **Console notifications** during operation
- **Log file alerts** for permanent record
- **Performance dashboard** visual indicators

## 🧪 Testing & Validation

### Run Comprehensive Tests
```bash
# Run all test suites
python run_all_tests.py

# Run specific test modules
python -m pytest test_monitoring_system.py -v
python -m pytest test_complete_system.py -v
```

### Test Coverage
- **Performance monitoring** functionality
- **Structured logging** system
- **Complete pipeline simulation** with mocked dependencies
- **Error handling** and resilience testing
- **Concurrent processing** validation

## 📋 Usage Examples

### Basic Monitoring Integration

```python
from monitoring import OperationTimer, get_main_logger, LogContext

logger = get_main_logger()

# Method 1: Using OperationTimer context manager
with OperationTimer('agent_name', 'operation_type', {'sku': 'ABC123'}):
    # Your operation code here
    result = some_operation()

# Method 2: Using LogContext for structured logging
with LogContext(logger, operation='image_search', sku='ABC123'):
    logger.info("Starting image search")
    # Operation code
    logger.success("Image search completed")
```

### Custom Performance Tracking

```python
from monitoring import performance_monitor

# Record instant metric
performance_monitor.record_instant_metric(
    agent='custom_agent',
    operation='custom_operation', 
    success=True,
    duration=1.5,
    metadata={'items_processed': 10}
)

# Get performance statistics
stats = performance_monitor.get_performance_stats(hours=24)
for operation, stat in stats.items():
    print(f"{operation}: {stat.success_rate:.2%} success rate")
```

## 📁 File Structure

```
monitoring/
├── __init__.py              # Package initialization and exports
├── performance_monitor.py   # Core performance tracking
├── logging_system.py       # Structured logging system
└── dashboard.py            # Streamlit monitoring dashboard

logs/                       # Generated log files
├── main.log               # Main application logs
├── main_structured.jsonl # JSON structured logs  
├── main_errors.log       # Error-specific logs
├── image_agent.log       # Image agent logs
├── vehicle_agent.log     # Vehicle application logs
└── bigcommerce_agent.log # BigCommerce agent logs

test_*.py                  # Comprehensive test suites
run_all_tests.py          # Test runner with reporting
```

## 🔍 Troubleshooting

### Common Issues

1. **Dashboard not loading**
   ```bash
   # Check if streamlit is installed
   pip install streamlit plotly pandas
   
   # Run dashboard with debug output
   streamlit run monitoring/dashboard.py --logger.level=debug
   ```

2. **No performance data showing**
   - Ensure operations have been run recently (last 24h)
   - Check that monitoring is properly integrated in main.py
   - Verify OperationTimer context managers are being used

3. **Log files not being created**
   - Check write permissions in the logs directory
   - Verify logging configuration in monitoring/logging_system.py
   - Ensure logger instances are being created properly

### Performance Tips

- **Monitor memory usage** during large batch processing
- **Use appropriate batch sizes** based on system resources
- **Configure log rotation** to prevent disk space issues
- **Regular cleanup** of old log files and exports

## 📚 Advanced Usage

### Custom Metrics Dashboard
You can extend the dashboard by adding custom metrics:

```python
# In monitoring/dashboard.py
def display_custom_metrics():
    # Add your custom visualization code
    pass
```

### Integration with External Systems
The monitoring system supports export to external monitoring platforms:

```python
# Export metrics for external analysis
performance_monitor.export_metrics('exports/metrics.json', hours=168)
```

---

**Need Help?** Check the test files for usage examples or review the monitoring system source code for advanced customization options.