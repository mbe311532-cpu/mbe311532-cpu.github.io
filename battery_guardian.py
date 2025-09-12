try:
    import psutil  # Optional
except Exception:
    psutil = None  # Fallbacks will be used when unavailable
import time
import threading
import json
import os
import platform
import subprocess
from datetime import datetime
from collections import deque
# Defer matplotlib import to plotting function to avoid hard dependency
try:
    import numpy as np  # Optional
except Exception:
    np = None
    
    def _mean(values):
        values_list = list(values)
        return sum(values_list) / len(values_list) if values_list else 0.0

    def _std(values):
        values_list = list(values)
        if len(values_list) <= 1:
            return 0.0
        m = _mean(values_list)
        var = sum((v - m) ** 2 for v in values_list) / len(values_list)
        return var ** 0.5
else:
    def _mean(values):
        return float(np.mean(list(values)))

    def _std(values):
        return float(np.std(list(values)))
from typing import Dict, List, Optional


class BatteryGuardian:
    """
    Comprehensive battery monitoring and management system
    with health tracking, optimization, and reporting features
    """

    def __init__(self, config_file: str = "battery_config.json"):
        self.config_file = config_file
        self.battery_history = deque(maxlen=1000)  # Store up to 1000 readings
        self.health_stats = {
            "charge_cycles": 0,
            "max_capacity": 100.0,
            "health_score": 100.0,
            "last_calibration": None,
        }
        self.is_monitoring = False
        self.monitor_thread = None

        # Load configuration
        self.load_config()

        # Initialize platform-specific settings
        self.detect_platform()

        print("BatteryGuardian initialized")

    def detect_platform(self) -> str:
        """Detect the current operating system"""
        system = platform.system().lower()
        if system == "windows":
            self.platform = "windows"
        elif system == "darwin":
            self.platform = "macos"
        elif system == "linux":
            # Try to detect desktop environment
            desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
            if "gnome" in desktop:
                self.platform = "linux_gnome"
            elif "kde" in desktop:
                self.platform = "linux_kde"
            else:
                self.platform = "linux"
        else:
            self.platform = "unknown"

        return self.platform

    def load_config(self) -> None:
        """Load configuration from file"""
        default_config = {
            "monitoring_interval": 60,  # seconds
            "health_check_interval": 3600,  # 1 hour
            "max_charging_limit": 80,
            "min_battery_level": 20,
            "notifications": {
                "low_battery": True,
                "charging_complete": True,
                "charging_started": True,
                "health_alert": True,
            },
            "power_saving_mode": False,
            "auto_optimize": True,
            "log_level": "info",
            "data_retention_days": 30,
        }

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    loaded_config = json.load(f)
                    self.config = {**default_config, **loaded_config}
            else:
                self.config = default_config
                self.save_config()
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = default_config

    def save_config(self) -> None:
        """Save configuration to file"""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_battery_info(self) -> Optional[Dict[str, object]]:
        """
        Get comprehensive battery information
        Returns: dict with battery stats or None if not available
        """
        try:
            battery = None
            if psutil is not None:
                try:
                    battery = psutil.sensors_battery()
                except Exception:
                    battery = None
            if battery is None:
                # Try Linux sysfs fallback
                if self.platform.startswith("linux"):
                    sysfs_info = self._get_battery_info_sysfs()
                    if sysfs_info is not None:
                        return sysfs_info
                return None

            return {
                "percent": float(battery.percent),
                "power_plugged": bool(battery.power_plugged),
                "seconds_left": getattr(battery, "secsleft", None),
                "timestamp": float(time.time()),
                "status": "charging" if battery.power_plugged else "discharging",
            }
        except Exception as e:
            print(f"Error getting battery info: {e}")
            return None

    def _get_battery_info_sysfs(self) -> Optional[Dict[str, object]]:
        """Linux-only: read battery info from /sys/class/power_supply"""
        try:
            base_path = "/sys/class/power_supply"
            if not os.path.isdir(base_path):
                return None
            battery_paths = []
            for entry in os.listdir(base_path):
                full_path = os.path.join(base_path, entry)
                if not os.path.isdir(full_path):
                    continue
                type_file = os.path.join(full_path, "type")
                try:
                    with open(type_file, "r") as f:
                        dev_type = f.read().strip().lower()
                    if dev_type == "battery" or entry.lower().startswith("bat"):
                        battery_paths.append(full_path)
                except Exception:
                    continue
            if not battery_paths:
                return None
            bat = battery_paths[0]
            capacity_file = os.path.join(bat, "capacity")
            status_file = os.path.join(bat, "status")
            try:
                with open(capacity_file, "r") as f:
                    percent = float(f.read().strip())
            except Exception:
                percent = None
            try:
                with open(status_file, "r") as f:
                    status_raw = f.read().strip()
            except Exception:
                status_raw = "Unknown"
            if percent is None:
                return None
            status_norm = status_raw.lower()
            power_plugged = status_norm in ("charging", "full", "not charging")
            return {
                "percent": percent,
                "power_plugged": power_plugged,
                "seconds_left": None,
                "timestamp": float(time.time()),
                "status": status_raw,
            }
        except Exception:
            return None

    def calculate_health_score(self) -> float:
        """
        Calculate battery health score based on usage patterns
        Returns: health score between 0-100
        """
        if not self.battery_history:
            return 100.0

        # Simple health calculation based on discharge patterns
        discharge_events: List[float] = []
        charging_events: List[float] = []

        for i in range(1, len(self.battery_history)):
            prev = self.battery_history[i - 1]
            curr = self.battery_history[i]

            if (not prev["power_plugged"]) and (not curr["power_plugged"]):
                # Discharging
                hours = max((curr["timestamp"] - prev["timestamp"]) / 3600.0, 1e-6)
                discharge_rate = (prev["percent"] - curr["percent"]) / hours  # percent per hour
                discharge_events.append(discharge_rate)

            elif prev["power_plugged"] and curr["power_plugged"]:
                # Charging
                hours = max((curr["timestamp"] - prev["timestamp"]) / 3600.0, 1e-6)
                charge_rate = (curr["percent"] - prev["percent"]) / hours
                charging_events.append(charge_rate)

        # Calculate health based on consistency of rates
        health_score = 100.0

        if discharge_events:
            discharge_std = _std(discharge_events)
            health_score -= min(discharge_std * 5.0, 30.0)  # Penalize inconsistent discharge

        if charging_events:
            charge_std = _std(charging_events)
            health_score -= min(charge_std * 5.0, 30.0)  # Penalize inconsistent charging

        return max(0.0, min(100.0, health_score))

    def optimize_power_usage(self) -> List[str]:
        """
        Suggest power optimization measures
        Returns: list of optimization suggestions
        """
        suggestions: List[str] = []

        try:
            # Check for high CPU processes
            processes: List[Dict[str, float]] = []
            if psutil is not None:
                for proc in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
                    try:
                        info = proc.as_dict(attrs=["name", "cpu_percent", "memory_percent"])
                        if info.get("cpu_percent", 0.0) > 10.0:
                            processes.append(info)
                    except Exception:
                        continue

            if processes:
                top_process = max(processes, key=lambda x: x.get("cpu_percent", 0.0))
                suggestions.append(
                    f"Close {top_process.get('name', 'Unknown')} (using {top_process.get('cpu_percent', 0.0):.1f}% CPU)"
                )

            # Check screen brightness (platform specific suggestions text only)
            if self.platform == "windows":
                suggestions.append("Reduce screen brightness to save power")
            elif self.platform == "macos":
                suggestions.append("Use Dark Mode and reduce brightness")

            # Network suggestions
            suggestions.append("Turn off Bluetooth and Wi-Fi if not needed")
            suggestions.append("Close unused browser tabs and applications")

        except Exception as e:
            print(f"Error in power optimization: {e}")

        return suggestions

    def apply_power_saving_mode(self, enable: bool = True) -> bool:
        """
        Apply power saving measures
        Returns: success status
        """
        try:
            if enable:
                print("Enabling power saving mode...")
                # Platform-specific power saving commands
                if self.platform == "windows":
                    subprocess.run(
                        [
                            "powercfg",
                            "/setactive",
                            "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
                        ],
                        check=False,
                    )  # Power saver
                elif self.platform == "macos":
                    subprocess.run(["pmset", "-a", "displaysleep", "5"], check=False)
                elif self.platform in ["linux_gnome", "linux_kde"]:
                    # Best-effort, only for GNOME schema; ignore failures
                    subprocess.run(
                        [
                            "gsettings",
                            "set",
                            "org.gnome.settings-daemon.plugins.power",
                            "sleep-inactive-battery-timeout",
                            "300",
                        ],
                        check=False,
                    )

                self.config["power_saving_mode"] = True
            else:
                print("Disabling power saving mode...")
                # Restore normal power settings
                if self.platform == "windows":
                    subprocess.run(
                        [
                            "powercfg",
                            "/setactive",
                            "381b4222-f694-41f0-9685-ff5bb260df2e",
                        ],
                        check=False,
                    )  # Balanced

                self.config["power_saving_mode"] = False

            self.save_config()
            return True

        except Exception as e:
            print(f"Error applying power saving mode: {e}")
            return False

    def generate_report(self, days: int = 7) -> Dict[str, object]:
        """
        Generate battery usage report
        Returns: comprehensive report dictionary
        """
        report: Dict[str, object] = {
            "period": f"last_{days}_days",
            "generated_at": datetime.now().isoformat(),
            "summary": {},
            "statistics": {},
            "recommendations": [],
        }

        # Filter data for the requested period
        cutoff_time = time.time() - (days * 86400)
        recent_data: List[Dict[str, object]] = [
            d for d in self.battery_history if d["timestamp"] > cutoff_time
        ]

        if not recent_data:
            report["summary"]["message"] = "No data available for the selected period"
            return report

        # Calculate statistics
        percentages = [float(d["percent"]) for d in recent_data]
        report["statistics"] = {
            "average_battery_level": _mean(percentages),
            "min_battery_level": float(min(percentages)),
            "max_battery_level": float(max(percentages)),
            "health_score": float(self.calculate_health_score()),
            "data_points": int(len(recent_data)),
        }

        # Calculate usage patterns
        charging_time = 0.0
        discharging_time = 0.0
        for i in range(1, len(recent_data)):
            time_diff = float(recent_data[i]["timestamp"] - recent_data[i - 1]["timestamp"])
            if recent_data[i]["power_plugged"]:
                charging_time += time_diff
            else:
                discharging_time += time_diff

        report["statistics"]["charging_time_hours"] = charging_time / 3600.0
        report["statistics"]["discharging_time_hours"] = discharging_time / 3600.0

        # Generate recommendations
        if report["statistics"]["min_battery_level"] < self.config["min_battery_level"]:
            report["recommendations"].append(
                f"Avoid discharging below {self.config['min_battery_level']}% to prolong battery life"
            )

        if report["statistics"]["health_score"] < 80:
            report["recommendations"].append(
                "Consider battery calibration and avoid extreme temperatures"
            )

        # Add optimization suggestions
        report["recommendations"].extend(self.optimize_power_usage())

        return report

    def plot_battery_usage(self, days: int = 1, save_path: Optional[str] = None) -> bool:
        """
        Create a battery usage plot
        Returns: success status
        """
        try:
            # Lazy import matplotlib to avoid hard dependency
            try:
                import matplotlib
                matplotlib.use("Agg", force=True)
                import matplotlib.pyplot as plt  # type: ignore
            except Exception as e:
                print(f"Plotting not available: {e}")
                return False

            # Filter data
            cutoff_time = time.time() - (days * 86400)
            recent_data = [d for d in self.battery_history if d["timestamp"] > cutoff_time]

            if not recent_data:
                print("No data available for plotting")
                return False

            # Prepare data
            timestamps = [datetime.fromtimestamp(float(d["timestamp"])) for d in recent_data]
            percentages = [float(d["percent"]) for d in recent_data]
            charging = [bool(d["power_plugged"]) for d in recent_data]

            # Create plot
            plt.figure(figsize=(12, 6))

            # Plot battery percentage
            plt.plot(timestamps, percentages, "b-", label="Battery Level", linewidth=2)

            # Highlight charging periods
            charging_start = None
            for i in range(len(timestamps)):
                if charging[i] and charging_start is None:
                    charging_start = timestamps[i]
                elif (not charging[i]) and (charging_start is not None):
                    plt.axvspan(
                        charging_start,
                        timestamps[i],
                        alpha=0.3,
                        color="green",
                        label="Charging" if i == 1 else "",
                    )
                    charging_start = None

            if charging_start is not None:
                plt.axvspan(charging_start, timestamps[-1], alpha=0.3, color="green")

            # Format plot
            plt.title(f"Battery Usage - Last {days} Day(s)")
            plt.xlabel("Time")
            plt.ylabel("Battery Percentage")
            plt.ylim(0, 100)
            plt.grid(True, alpha=0.3)
            plt.legend()

            # Rotate x-axis labels for better readability
            plt.xticks(rotation=45)
            plt.tight_layout()

            # Save or show
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches="tight")
                print(f"Plot saved to {save_path}")
            else:
                plt.show()

            plt.close()
            return True

        except Exception as e:
            print(f"Error creating plot: {e}")
            return False

    def monitor_battery(self) -> None:
        """Main battery monitoring loop"""
        health_check_counter = 0

        while self.is_monitoring:
            try:
                # Get current battery info
                battery_info = self.get_battery_info()
                if battery_info:
                    self.battery_history.append(battery_info)

                    # Check for notifications
                    self.check_notifications(battery_info)

                    # Auto-optimize if enabled
                    if (
                        self.config["auto_optimize"]
                        and (not battery_info["power_plugged"])
                        and battery_info["percent"] < 30
                    ):
                        self.apply_power_saving_mode(True)

                # Periodic health check
                health_check_counter += int(self.config["monitoring_interval"])
                if health_check_counter >= int(self.config["health_check_interval"]):
                    self.update_health_stats()
                    health_check_counter = 0

                # Sleep until next check
                time.sleep(float(self.config["monitoring_interval"]))

            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(5)  # Wait before retrying

    def check_notifications(self, battery_info: Dict[str, object]) -> None:
        """Check and trigger notifications based on battery state"""
        if not self.config["notifications"]["low_battery"]:
            return

        # Low battery warning
        if (not battery_info["power_plugged"]) and (
            battery_info["percent"] <= self.config["min_battery_level"]
        ):
            self.send_notification(
                "Low Battery Warning",
                f"Battery level is at {battery_info['percent']}%. Connect to power soon.",
            )

        # Charging complete
        if (
            self.config["notifications"]["charging_complete"]
            and battery_info["power_plugged"]
            and battery_info["percent"] >= 95
        ):
            self.send_notification(
                "Charging Complete",
                "Battery is fully charged. You can unplug the charger.",
            )

    def send_notification(self, title: str, message: str) -> None:
        """Send system notification"""
        try:
            if self.platform == "windows":
                try:
                    from win10toast import ToastNotifier

                    toaster = ToastNotifier()
                    toaster.show_toast(title, message, duration=5)
                except Exception:
                    print(f"{title}: {message}")
            elif self.platform == "macos":
                subprocess.run(
                    ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
                    check=False,
                )
            elif self.platform.startswith("linux"):
                subprocess.run(["notify-send", title, message], check=False)
            else:
                print(f"{title}: {message}")
        except Exception as e:
            print(f"Notification error: {e}")
            print(f"{title}: {message}")  # Fallback to console

    def update_health_stats(self) -> None:
        """Update battery health statistics"""
        self.health_stats["health_score"] = self.calculate_health_score()
        # Additional health calculations can be added here

    def start_monitoring(self) -> bool:
        """Start battery monitoring"""
        if self.is_monitoring:
            print("Monitoring is already running")
            return False

        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_battery, daemon=True)
        self.monitor_thread.start()

        print("Battery monitoring started")
        return True

    def stop_monitoring(self) -> None:
        """Stop battery monitoring"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("Battery monitoring stopped")

    def get_status(self) -> Dict[str, object]:
        """Get current battery status"""
        battery_info = self.get_battery_info()
        if not battery_info:
            return {"error": "Battery information not available"}

        status: Dict[str, object] = {
            "current_level": battery_info["percent"],
            "is_charging": battery_info["power_plugged"],
            "health_score": self.health_stats["health_score"],
            "time_remaining": self.estimate_time_remaining(),
            "power_saving_mode": self.config["power_saving_mode"],
            "timestamp": datetime.now().isoformat(),
        }

        return status

    def estimate_time_remaining(self) -> Optional[str]:
        """Estimate time remaining based on historical data"""
        if not self.battery_history:
            return None

        current = self.battery_history[-1]
        if current["power_plugged"]:
            # Estimate charging time
            return self.estimate_charging_time()
        else:
            # Estimate discharging time
            return self.estimate_discharging_time()

    def estimate_charging_time(self) -> str:
        """Estimate time until fully charged"""
        current = self.battery_history[-1]
        remaining_percent = max(0.0, 100.0 - float(current["percent"]))

        # Average charge rate: ~1-2% per minute
        minutes = remaining_percent * 1.5
        return f"{int(minutes // 60)}h {int(minutes % 60)}m"

    def estimate_discharging_time(self) -> str:
        """Estimate time until battery depletion"""
        # Calculate average discharge rate from history
        discharge_rates: List[float] = []
        for i in range(1, len(self.battery_history)):
            prev = self.battery_history[i - 1]
            curr = self.battery_history[i]

            if (not prev["power_plugged"]) and (not curr["power_plugged"]):
                time_diff_min = max((float(curr["timestamp"]) - float(prev["timestamp"])) / 60.0, 1e-6)
                percent_diff = float(prev["percent"]) - float(curr["percent"])  # positive during discharge
                if (time_diff_min > 0.0) and (percent_diff > 0.0):
                    discharge_rates.append(percent_diff / time_diff_min)  # % per minute

        if not discharge_rates:
            return "Unknown"

        avg_discharge_rate = float(sum(discharge_rates) / len(discharge_rates))
        if avg_discharge_rate <= 0.0:
            return "Unknown"

        current = self.battery_history[-1]
        minutes_remaining = float(current["percent"]) / avg_discharge_rate
        return f"{int(minutes_remaining // 60)}h {int(minutes_remaining % 60)}m"

    def cleanup_old_data(self) -> None:
        """Clean up data older than retention period"""
        retention_seconds = int(self.config["data_retention_days"]) * 86400
        cutoff_time = time.time() - retention_seconds

        # Remove old entries from history
        while self.battery_history and (self.battery_history[0]["timestamp"] < cutoff_time):
            self.battery_history.popleft()

        print(f"Cleaned up data older than {self.config['data_retention_days']} days")


def main() -> None:
    """Main function with CLI interface"""
    battery_guardian = BatteryGuardian()

    print("BatteryGuardian - Comprehensive Battery Management")
    print("=" * 50)

    # Start monitoring
    battery_guardian.start_monitoring()

    try:
        while True:
            print("\nOptions:")
            print("1. Show current status")
            print("2. Generate report")
            print("3. Optimize power usage")
            print("4. Toggle power saving mode")
            print("5. Create usage plot")
            print("6. Exit")

            choice = input("\nEnter your choice (1-6): ").strip()

            if choice == "1":
                status = battery_guardian.get_status()
                print(f"\nCurrent Battery Status:")
                if "error" in status:
                    print(f"  {status['error']}")
                else:
                    print(f"  Level: {status['current_level']}%")
                    print(f"  Charging: {'Yes' if status['is_charging'] else 'No'}")
                    print(f"  Health Score: {status['health_score']:.1f}/100")
                    print(f"  Time Remaining: {status['time_remaining']}")
                    print(
                        f"  Power Saving: {'Enabled' if status['power_saving_mode'] else 'Disabled'}"
                    )

            elif choice == "2":
                days_raw = input("Enter number of days for report (default 7): ").strip()
                days = int(days_raw) if days_raw.isdigit() else 7
                report = battery_guardian.generate_report(days)

                if "statistics" not in report or not report["statistics"]:
                    print("\nBattery Report: No data available")
                else:
                    print(f"\nBattery Report - Last {days} Days:")
                    stats = report["statistics"]
                    print(f"  Average Level: {stats['average_battery_level']:.1f}%")
                    print(f"  Health Score: {stats['health_score']:.1f}/100")
                    print(f"  Charging Time: {stats['charging_time_hours']:.1f}h")
                    print(f"  Recommendations:")
                    for rec in report["recommendations"]:
                        print(f"    • {rec}")

            elif choice == "3":
                suggestions = battery_guardian.optimize_power_usage()
                print("\nPower Optimization Suggestions:")
                for suggestion in suggestions:
                    print(f"  • {suggestion}")

            elif choice == "4":
                current_mode = bool(battery_guardian.config["power_saving_mode"])
                new_mode = not current_mode
                success = battery_guardian.apply_power_saving_mode(new_mode)
                if success:
                    status_text = "enabled" if new_mode else "disabled"
                    print(f"Power saving mode {status_text}")
                else:
                    print("Failed to change power saving mode")

            elif choice == "5":
                days_raw = input("Enter number of days to plot (default 1): ").strip()
                days = int(days_raw) if days_raw.isdigit() else 1
                filename = f"battery_usage_{days}days.png"
                success = battery_guardian.plot_battery_usage(days, filename)
                if success:
                    print(f"Plot saved as {filename}")
                else:
                    print("Failed to create plot")

            elif choice == "6":
                break

            else:
                print("Invalid choice. Please try again.")

            # Brief pause
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        battery_guardian.stop_monitoring()
        print("BatteryGuardian stopped")


if __name__ == "__main__":
    # Avoid running interactive CLI during automated checks
    if os.environ.get("BG_NON_INTERACTIVE", "0") == "1":
        # Minimal smoke test
        bg = BatteryGuardian()
        status = bg.get_status()
        print(json.dumps(status))
    else:
        main()