from apscheduler.schedulers.background import BackgroundScheduler
from ppm_daily_mailer import send_today_schedule
from datetime import datetime, timedelta  # ✅ FIXED: Added timedelta import

def start_ppm_scheduler():
    """Start the APScheduler for daily maintenance emails"""
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    
    # Schedule email to be sent every day at 8:30 AM IST
    scheduler.add_job(
        func=send_today_schedule,
        trigger="cron",
        hour=8,
        minute=30,
        id='daily_maintenance_email',
        replace_existing=True,
        misfire_grace_time=3600  # 1 hour grace period
    )
    
    # Add a test job that runs 1 minute after startup (for testing)
    scheduler.add_job(
        func=send_today_schedule,
        trigger="date",
        run_date=datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=1),
        id='test_email',
        replace_existing=True
    )
    
    scheduler.start()
    print("✅ PPM Scheduler started successfully")
    print("📧 Daily emails scheduled for 8:30 AM IST")
    print("🧪 Test email will be sent in 1 minute")
    return scheduler  # Return scheduler for proper cleanup if needed

if __name__ == "__main__":
    scheduler = start_ppm_scheduler()
    
    # Keep the script running
    try:
        import time
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("🛑 PPM Scheduler stopped")