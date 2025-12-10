"""
Live Match Display UI
Provides rich console display with probability visualization and updates.
"""
import os
import sys
from typing import Dict, Any, List
from datetime import datetime
import time


class LiveMatchDisplay:
    """
    Enhanced console display for live match predictions with visual elements.
    """
    
    def __init__(self, clear_screen: bool = True):
        """
        Initialize display.
        
        Args:
            clear_screen: Whether to clear screen between updates
        """
        self.clear_screen = clear_screen
        self.history = []
        self.max_history = 10  # Show last 10 balls
        
    def clear(self):
        """Clear the console screen."""
        if self.clear_screen:
            os.system('cls' if os.name == 'nt' else 'clear')
    
    def display_prediction(self, result: Dict[str, Any]):
        """
        Display prediction result with rich formatting.
        
        Args:
            result: Prediction result dictionary
        """
        if 'error' in result:
            self._display_error(result)
            return
        
        # Add to history
        self.history.append(result)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        # Clear and redraw
        self.clear()
        
        # Header
        self._display_header(result)
        
        # Main probability display
        self._display_probability(result)
        
        # Match situation
        self._display_situation(result)
        
        # Probability trend
        self._display_trend()
        
        # Key metrics
        self._display_metrics(result)
        
        # Recent history
        self._display_history()
        
        # Footer
        self._display_footer()
    
    def _display_header(self, result: Dict[str, Any]):
        """Display match header."""
        print("\n" + "═" * 100)
        print(f"{'🏏 LIVE CRICKET MATCH PREDICTION':^100}")
        print("═" * 100)
        
        batting = result.get('batting_team', 'Unknown')
        bowling = result.get('bowling_team', 'Unknown')
        innings = result.get('innings', 1)
        
        print(f"\n{'Innings':<15}: {innings}")
        print(f"{'Batting':<15}: {batting}")
        print(f"{'Bowling':<15}: {bowling}")
        print(f"{'Current Ball':<15}: Over {result['ball']}")
        print()
    
    def _display_probability(self, result: Dict[str, Any]):
        """Display win probability with visual bar."""
        win_prob = result['win_probability']
        batting_team = result.get('batting_team', 'Batting Team')
        
        print("─" * 100)
        print(f"\n{'WIN PROBABILITY':^100}\n")
        
        # Color based on probability
        if win_prob > 0.7:
            emoji = "🔥🔥🔥"
            desc = "STRONG FAVORITE"
        elif win_prob > 0.6:
            emoji = "🔥🔥"
            desc = "FAVORITE"
        elif win_prob > 0.5:
            emoji = "📈"
            desc = "SLIGHT EDGE"
        elif win_prob > 0.4:
            emoji = "📉"
            desc = "SLIGHT DISADVANTAGE"
        elif win_prob > 0.3:
            emoji = "❄️❄️"
            desc = "UNDERDOG"
        else:
            emoji = "❄️❄️❄️"
            desc = "STRONG UNDERDOG"
        
        # Progress bar
        bar_length = 60
        filled = int(bar_length * win_prob)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        print(f"{batting_team}: {win_prob:.1%} {emoji}")
        print(f"[{bar}]")
        print(f"{desc:^100}\n")
        
        # Model vs DLS comparison
        resource_prob = result.get('resource_win_prob', 0.5)
        diff = win_prob - resource_prob
        if abs(diff) > 0.05:
            direction = "more optimistic" if diff > 0 else "more pessimistic"
            print(f"📊 Model is {direction} than DLS baseline by {abs(diff):.1%}")
        print()
    
    def _display_situation(self, result: Dict[str, Any]):
        """Display current match situation."""
        print("─" * 100)
        print(f"\n{'MATCH SITUATION':^100}\n")
        
        score = result['score']
        innings = result['innings']
        
        print(f"{'Score':<30}: {score}")
        
        if innings == 2:
            runs_req = result.get('runs_required')
            balls_rem = result.get('balls_remaining')
            req_rr = result.get('required_run_rate')
            curr_rr = result.get('current_run_rate')
            
            if runs_req is not None:
                overs_rem = balls_rem / 6
                print(f"{'Target':<30}: {runs_req} runs from {balls_rem} balls ({overs_rem:.1f} overs)")
                print(f"{'Required Run Rate':<30}: {req_rr:.2f}")
                print(f"{'Current Run Rate':<30}: {curr_rr:.2f}")
                
                # Run rate comparison
                rr_diff = req_rr - curr_rr
                if rr_diff > 2:
                    print(f"{'Status':<30}: ⚠️  Well behind the rate (need {rr_diff:.2f} more per over)")
                elif rr_diff > 0:
                    print(f"{'Status':<30}: 📊 Slightly behind the rate (need {rr_diff:.2f} more per over)")
                elif rr_diff > -1:
                    print(f"{'Status':<30}: ✅ On track!")
                else:
                    print(f"{'Status':<30}: 🎯 Ahead of the rate!")
        else:
            exp_score = result.get('expected_final_score', 0)
            curr_rr = result.get('current_run_rate', 0)
            balls_rem = result.get('balls_remaining', 0)
            overs_rem = balls_rem / 6
            
            print(f"{'Expected Final Score':<30}: {exp_score}")
            print(f"{'Current Run Rate':<30}: {curr_rr:.2f}")
            print(f"{'Overs Remaining':<30}: {overs_rem:.1f}")
        
        # Pressure index
        pressure = result.get('pressure_index', 0)
        pressure_bar_len = int(50 * pressure)
        pressure_bar = "▓" * pressure_bar_len + "░" * (50 - pressure_bar_len)
        print(f"\n{'Pressure Index':<30}: [{pressure_bar}] {pressure:.2f}")
        
        if pressure > 0.7:
            print(f"{'Pressure Level':<30}: 🔴 EXTREME PRESSURE")
        elif pressure > 0.5:
            print(f"{'Pressure Level':<30}: 🟠 HIGH PRESSURE")
        elif pressure > 0.3:
            print(f"{'Pressure Level':<30}: 🟡 MODERATE PRESSURE")
        else:
            print(f"{'Pressure Level':<30}: 🟢 LOW PRESSURE")
        print()
    
    def _display_trend(self):
        """Display probability trend over recent balls."""
        if len(self.history) < 2:
            return
        
        print("─" * 100)
        print(f"\n{'PROBABILITY TREND (Last {len(self.history)} balls)':^100}\n")
        
        # Simple ASCII chart
        max_prob = max(h['win_probability'] for h in self.history)
        min_prob = min(h['win_probability'] for h in self.history)
        
        # Normalize to 0-20 range for display
        chart_height = 15
        
        for i in range(chart_height, -1, -1):
            line = ""
            for h in self.history:
                prob = h['win_probability']
                norm_prob = int(((prob - min_prob) / (max_prob - min_prob + 0.01)) * chart_height)
                if norm_prob >= i:
                    line += "█ "
                else:
                    line += "  "
            
            # Y-axis label
            prob_val = min_prob + (max_prob - min_prob) * (i / chart_height)
            print(f"{prob_val:>5.1%} │ {line}")
        
        print("      └" + "──" * len(self.history))
        
        # X-axis labels (ball numbers)
        x_labels = "       "
        for h in self.history:
            ball_num = h['ball'].split('.')[-1]
            x_labels += f"{ball_num} "
        print(x_labels)
        print()
    
    def _display_metrics(self, result: Dict[str, Any]):
        """Display key metrics."""
        print("─" * 100)
        print(f"\n{'KEY METRICS':^100}\n")
        
        metrics = [
            ("Wickets Remaining", result.get('wickets_remaining', 0)),
            ("Balls Remaining", result.get('balls_remaining', 0)),
            ("Resource %", f"{result.get('resource_win_prob', 0):.1%}"),
        ]
        
        # Display in columns
        col_width = 30
        for i in range(0, len(metrics), 3):
            row_metrics = metrics[i:i+3]
            line = ""
            for name, value in row_metrics:
                line += f"{name:<20}: {str(value):<8} "
            print(line)
        print()
    
    def _display_history(self):
        """Display recent prediction history."""
        if len(self.history) < 2:
            return
        
        print("─" * 100)
        print(f"\n{'RECENT BALLS':^100}\n")
        
        print(f"{'Ball':<12} {'Score':<15} {'Win Prob':<12} {'Pressure':<12} {'Change':<12}")
        print("─" * 100)
        
        for i, h in enumerate(self.history[-5:]):  # Last 5 balls
            ball = h['ball']
            score = h['score']
            prob = h['win_probability']
            pressure = h.get('pressure_index', 0)
            
            # Calculate change from previous
            if i > 0:
                prev_prob = self.history[-6+i]['win_probability']
                change = prob - prev_prob
                if abs(change) < 0.01:
                    change_str = "─"
                elif change > 0:
                    change_str = f"📈 +{change:.1%}"
                else:
                    change_str = f"📉 {change:.1%}"
            else:
                change_str = "─"
            
            print(f"{ball:<12} {score:<15} {prob:<11.1%} {pressure:<11.2f} {change_str:<12}")
        print()
    
    def _display_footer(self):
        """Display footer with timestamp and instructions."""
        print("═" * 100)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{'Last Updated':<50}: {timestamp}")
        print(f"{'Press Ctrl+C to stop':^100}")
        print("═" * 100 + "\n")
    
    def _display_error(self, result: Dict[str, Any]):
        """Display error message."""
        print("\n" + "❌" * 50)
        print(f"\nError: {result.get('error', 'Unknown error')}")
        print(f"Timestamp: {result.get('timestamp', 'N/A')}\n")
        print("❌" * 50 + "\n")


# Simple text-based progress indicator for terminal
class ProgressIndicator:
    """Animated loading indicator for terminal."""
    
    def __init__(self, message: str = "Waiting for next ball"):
        self.message = message
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.current = 0
        self.running = False
    
    def start(self):
        """Start the indicator."""
        self.running = True
        self._animate()
    
    def stop(self):
        """Stop the indicator."""
        self.running = False
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()
    
    def _animate(self):
        """Animate the indicator (call in loop)."""
        if self.running:
            frame = self.frames[self.current % len(self.frames)]
            sys.stdout.write(f"\r{frame} {self.message}...")
            sys.stdout.flush()
            self.current += 1
            time.sleep(0.1)
