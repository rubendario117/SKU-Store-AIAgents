#!/usr/bin/env python3
"""
Monitoring dashboard for DPerformance Agent
Provides real-time metrics and performance analytics
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Any

from monitoring.performance_monitor import performance_monitor
from monitoring.logging_system import get_logger

def display_system_overview():
    """Display system overview metrics"""
    st.header("📊 System Performance Overview")
    
    # Get performance stats for last 24 hours
    stats = performance_monitor.get_performance_stats(hours=24)
    
    if not stats:
        st.warning("No performance data available yet. Run some operations to see metrics.")
        return
    
    # Calculate overall metrics
    total_ops = sum(stat.total_operations for stat in stats.values())
    total_successful = sum(stat.successful_operations for stat in stats.values())
    overall_success_rate = (total_successful / total_ops * 100) if total_ops > 0 else 0
    avg_duration = sum(stat.average_duration * stat.total_operations for stat in stats.values()) / total_ops if total_ops > 0 else 0
    
    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Operations (24h)", total_ops)
    
    with col2:
        st.metric("Success Rate", f"{overall_success_rate:.1f}%", 
                 delta=f"{overall_success_rate - 90:.1f}%" if overall_success_rate > 90 else None)
    
    with col3:
        st.metric("Avg Duration", f"{avg_duration:.2f}s")
    
    with col4:
        active_ops = len(performance_monitor.active_operations)
        st.metric("Active Operations", active_ops)

def display_agent_performance():
    """Display per-agent performance metrics"""
    st.header("🤖 Agent Performance Breakdown")
    
    stats = performance_monitor.get_performance_stats(hours=24)
    
    if not stats:
        return
    
    # Prepare data for visualization
    agent_data = []
    for key, stat in stats.items():
        agent, operation = key.split('_', 1)
        agent_data.append({
            'Agent': agent,
            'Operation': operation,
            'Total Operations': stat.total_operations,
            'Success Rate': stat.success_rate * 100,
            'Avg Duration': stat.average_duration,
            'Failed Operations': stat.failed_operations
        })
    
    df = pd.DataFrame(agent_data)
    
    if df.empty:
        return
    
    # Success rate by agent
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Success Rate by Agent")
        fig_success = px.bar(df, x='Agent', y='Success Rate', color='Operation',
                           title="Success Rate by Agent and Operation")
        fig_success.update_layout(yaxis_range=[0, 100])
        st.plotly_chart(fig_success, use_container_width=True)
    
    with col2:
        st.subheader("Average Duration by Agent")
        fig_duration = px.bar(df, x='Agent', y='Avg Duration', color='Operation',
                            title="Average Duration by Agent and Operation")
        st.plotly_chart(fig_duration, use_container_width=True)
    
    # Detailed table
    st.subheader("Detailed Performance Metrics")
    st.dataframe(df, use_container_width=True)

def display_failure_analysis():
    """Display failure analysis"""
    st.header("🔍 Failure Analysis")
    
    failures = performance_monitor.get_recent_failures(hours=24, limit=50)
    
    if not failures:
        st.success("No failures in the last 24 hours! 🎉")
        return
    
    # Prepare failure data
    failure_data = []
    for failure in failures:
        failure_data.append({
            'Timestamp': datetime.fromtimestamp(failure.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'Agent': failure.agent,
            'Operation': failure.operation,
            'Duration': f"{failure.duration:.2f}s",
            'Error': failure.metadata.get('error', 'Unknown error')
        })
    
    failure_df = pd.DataFrame(failure_data)
    
    # Failure count by agent
    col1, col2 = st.columns(2)
    
    with col1:
        failure_counts = failure_df['Agent'].value_counts()
        fig_failures = px.pie(values=failure_counts.values, names=failure_counts.index,
                            title="Failures by Agent")
        st.plotly_chart(fig_failures, use_container_width=True)
    
    with col2:
        # Failure timeline
        failure_df['Hour'] = pd.to_datetime(failure_df['Timestamp']).dt.floor('H')
        hourly_failures = failure_df.groupby('Hour').size().reset_index(name='Failures')
        fig_timeline = px.line(hourly_failures, x='Hour', y='Failures',
                             title="Failures Over Time")
        st.plotly_chart(fig_timeline, use_container_width=True)
    
    # Recent failures table
    st.subheader("Recent Failures")
    st.dataframe(failure_df, use_container_width=True)

def display_performance_trends():
    """Display performance trends over time"""
    st.header("📈 Performance Trends")
    
    # Get metrics from different time periods
    periods = [1, 6, 24, 168]  # 1h, 6h, 24h, 1 week
    trend_data = []
    
    for hours in periods:
        stats = performance_monitor.get_performance_stats(hours=hours)
        if stats:
            total_ops = sum(stat.total_operations for stat in stats.values())
            successful_ops = sum(stat.successful_operations for stat in stats.values())
            success_rate = (successful_ops / total_ops * 100) if total_ops > 0 else 0
            avg_duration = sum(stat.average_duration * stat.total_operations for stat in stats.values()) / total_ops if total_ops > 0 else 0
            
            period_label = f"{hours}h" if hours < 24 else f"{hours//24}d"
            trend_data.append({
                'Period': period_label,
                'Hours': hours,
                'Total Operations': total_ops,
                'Success Rate': success_rate,
                'Average Duration': avg_duration
            })
    
    if trend_data:
        trend_df = pd.DataFrame(trend_data)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_ops = px.line(trend_df, x='Period', y='Total Operations',
                            title="Operations Volume by Time Period")
            st.plotly_chart(fig_ops, use_container_width=True)
        
        with col2:
            fig_success_trend = px.line(trend_df, x='Period', y='Success Rate',
                                      title="Success Rate Trend")
            fig_success_trend.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig_success_trend, use_container_width=True)

def display_log_analysis():
    """Display log file analysis"""
    st.header("📄 Log Analysis")
    
    logs_dir = "logs"
    
    if not os.path.exists(logs_dir):
        st.warning("No log directory found. Run some operations to generate logs.")
        return
    
    # List available log files
    log_files = []
    for filename in os.listdir(logs_dir):
        if filename.endswith('.log') or filename.endswith('.jsonl'):
            filepath = os.path.join(logs_dir, filename)
            size = os.path.getsize(filepath)
            modified = datetime.fromtimestamp(os.path.getmtime(filepath))
            log_files.append({
                'Filename': filename,
                'Size': f"{size / 1024:.1f} KB",
                'Last Modified': modified.strftime('%Y-%m-%d %H:%M:%S'),
                'Path': filepath
            })
    
    if not log_files:
        st.info("No log files found.")
        return
    
    log_df = pd.DataFrame(log_files)
    st.dataframe(log_df.drop('Path', axis=1), use_container_width=True)
    
    # Log file viewer
    st.subheader("Log File Viewer")
    selected_file = st.selectbox("Select log file to view:", 
                                options=log_df['Filename'].tolist())
    
    if selected_file:
        selected_path = log_df[log_df['Filename'] == selected_file]['Path'].iloc[0]
        
        try:
            with open(selected_path, 'r') as f:
                # Read last 100 lines
                lines = f.readlines()
                recent_lines = lines[-100:] if len(lines) > 100 else lines
                content = ''.join(recent_lines)
            
            st.text_area("Log Content (Last 100 lines):", content, height=300)
            
        except Exception as e:
            st.error(f"Error reading log file: {e}")

def export_metrics():
    """Export metrics functionality"""
    st.header("📤 Export Metrics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        hours = st.selectbox("Time period:", [1, 6, 24, 168, 720], 
                           format_func=lambda x: f"{x} hours" if x < 24 else f"{x//24} days")
    
    with col2:
        if st.button("Export Metrics to JSON"):
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                export_path = f"exports/metrics_export_{timestamp}.json"
                
                os.makedirs("exports", exist_ok=True)
                performance_monitor.export_metrics(export_path, hours=hours)
                
                st.success(f"Metrics exported to {export_path}")
                
                # Offer download
                with open(export_path, 'r') as f:
                    st.download_button(
                        label="Download Export File",
                        data=f.read(),
                        file_name=os.path.basename(export_path),
                        mime="application/json"
                    )
                    
            except Exception as e:
                st.error(f"Export failed: {e}")

def main_dashboard():
    """Main dashboard function"""
    st.set_page_config(
        page_title="DPerformance Agent - Monitoring Dashboard",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 DPerformance Agent - Monitoring Dashboard")
    st.markdown("Real-time performance monitoring and analytics")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Choose a page:", [
        "System Overview",
        "Agent Performance", 
        "Failure Analysis",
        "Performance Trends",
        "Log Analysis",
        "Export Metrics"
    ])
    
    # Auto-refresh option
    auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)")
    if auto_refresh:
        st.sidebar.info("Dashboard will auto-refresh every 30 seconds")
        # Note: In production, you'd use st.rerun() with a timer
    
    # Display selected page
    if page == "System Overview":
        display_system_overview()
    elif page == "Agent Performance":
        display_agent_performance()
    elif page == "Failure Analysis":
        display_failure_analysis()
    elif page == "Performance Trends":
        display_performance_trends()
    elif page == "Log Analysis":
        display_log_analysis()
    elif page == "Export Metrics":
        export_metrics()
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.info("💡 Tip: Run operations in the main app to see real-time metrics here!")

if __name__ == "__main__":
    main_dashboard()