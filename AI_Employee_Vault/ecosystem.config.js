# PM2 Ecosystem Configuration for AI Employee Watchers
# Usage: pm2 start ecosystem.config.js

module.exports = {
  apps: [
    {
      name: "fb-ig-watcher",
      script: "./Watchers/facebook_instagram_watcher.py",
      interpreter: "python",
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: "500M",
      env: {
        PYTHONUNBUFFERED: "1",
      },
      error_file: "./Logs/pm2_fb_ig_error.log",
      out_file: "./Logs/pm2_fb_ig_out.log",
      log_file: "./Logs/pm2_fb_ig_combined.log",
      time: true,
    },
    {
      name: "twitter-watcher",
      script: "./Watchers/twitter_watcher.py",
      interpreter: "python",
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: "500M",
      env: {
        PYTHONUNBUFFERED: "1",
      },
      error_file: "./Logs/pm2_twitter_error.log",
      out_file: "./Logs/pm2_twitter_out.log",
      log_file: "./Logs/pm2_twitter_combined.log",
      time: true,
    },
    {
      name: "gmail-watcher",
      script: "./Watchers/gmail_watcher.py",
      interpreter: "python",
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: "300M",
      env: {
        PYTHONUNBUFFERED: "1",
      },
      error_file: "./Logs/pm2_gmail_error.log",
      out_file: "./Logs/pm2_gmail_out.log",
      log_file: "./Logs/pm2_gmail_combined.log",
      time: true,
    },
  ],
};
