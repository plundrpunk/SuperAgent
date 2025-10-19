#!/usr/bin/env python3
"""
Kaya Quick Access GUI
Simple GUI with button and keyboard shortcut to activate Kaya
"""
import tkinter as tk
from tkinter import ttk
import subprocess
import threading
import sys
import os

class KayaQuickAccess:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Kaya Quick Access")
        self.root.geometry("400x300")
        self.root.configure(bg='#1e1e1e')

        # Make window always on top (optional - can be toggled)
        self.always_on_top = tk.BooleanVar(value=True)
        self.root.attributes('-topmost', self.always_on_top.get())

        # Setup UI
        self.setup_ui()

        # Keyboard shortcuts
        self.setup_shortcuts()

        # Position window in top-right corner
        self.position_window()

    def setup_ui(self):
        """Create the UI elements"""
        # Main container
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)

        # Title
        title = tk.Label(
            main_frame,
            text="🤖 Kaya",
            font=('Arial', 24, 'bold'),
            bg='#1e1e1e',
            fg='#00ff88'
        )
        title.pack(pady=(0, 20))

        # Status label
        self.status_label = tk.Label(
            main_frame,
            text="Ready to listen",
            font=('Arial', 12),
            bg='#1e1e1e',
            fg='#888888'
        )
        self.status_label.pack(pady=(0, 20))

        # Big "Execute Mission" button
        self.execute_button = tk.Button(
            main_frame,
            text="🚀 Execute Mission",
            font=('Arial', 16, 'bold'),
            bg='#00ff88',
            fg='#1e1e1e',
            activebackground='#00cc66',
            activeforeground='#1e1e1e',
            relief='flat',
            bd=0,
            padx=30,
            pady=15,
            cursor='hand2',
            command=lambda: self.quick_command("execute the mission")
        )
        self.execute_button.pack(pady=10)

        # Secondary buttons row
        button_row = tk.Frame(main_frame, bg='#1e1e1e')
        button_row.pack(pady=(10, 0))

        tk.Button(
            button_row,
            text="Fix All Tests",
            font=('Arial', 11),
            bg='#2d2d2d',
            fg='#00ff88',
            activebackground='#3d3d3d',
            relief='flat',
            bd=0,
            padx=15,
            pady=8,
            cursor='hand2',
            command=lambda: self.quick_command("fix all test failures")
        ).pack(side='left', padx=5)

        tk.Button(
            button_row,
            text="Status",
            font=('Arial', 11),
            bg='#2d2d2d',
            fg='#00ff88',
            activebackground='#3d3d3d',
            relief='flat',
            bd=0,
            padx=15,
            pady=8,
            cursor='hand2',
            command=lambda: self.quick_command("status")
        ).pack(side='left', padx=5)

        # Shortcut hint
        shortcut_hint = tk.Label(
            main_frame,
            text="Shortcut: Ctrl+Shift+E (Execute)",
            font=('Arial', 10),
            bg='#1e1e1e',
            fg='#666666'
        )
        shortcut_hint.pack(pady=(10, 0))

        # Command input (alternative to voice)
        input_frame = tk.Frame(main_frame, bg='#1e1e1e')
        input_frame.pack(pady=(20, 0), fill='x')

        tk.Label(
            input_frame,
            text="Or type a command:",
            font=('Arial', 10),
            bg='#1e1e1e',
            fg='#888888'
        ).pack(anchor='w')

        self.command_entry = tk.Entry(
            input_frame,
            font=('Arial', 12),
            bg='#2d2d2d',
            fg='#ffffff',
            insertbackground='#00ff88',
            relief='flat',
            bd=0
        )
        self.command_entry.pack(fill='x', pady=(5, 0), ipady=8)
        self.command_entry.bind('<Return>', self.send_text_command)

        # Options
        options_frame = tk.Frame(main_frame, bg='#1e1e1e')
        options_frame.pack(pady=(20, 0))

        self.always_on_top_check = tk.Checkbutton(
            options_frame,
            text="Always on top",
            variable=self.always_on_top,
            command=self.toggle_always_on_top,
            bg='#1e1e1e',
            fg='#888888',
            selectcolor='#2d2d2d',
            activebackground='#1e1e1e',
            activeforeground='#00ff88'
        )
        self.always_on_top_check.pack(side='left', padx=5)

    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Ctrl+Shift+E to execute mission
        self.root.bind('<Control-Shift-E>', lambda e: self.quick_command("execute the mission"))

        # Ctrl+Shift+F to fix all tests
        self.root.bind('<Control-Shift-F>', lambda e: self.quick_command("fix all test failures"))

        # Escape to close
        self.root.bind('<Escape>', lambda e: self.root.quit())

    def position_window(self):
        """Position window in top-right corner"""
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()

        x = screen_width - window_width - 20
        y = 20

        self.root.geometry(f"+{x}+{y}")

    def toggle_always_on_top(self):
        """Toggle always on top setting"""
        self.root.attributes('-topmost', self.always_on_top.get())

    def quick_command(self, command):
        """Execute a quick command"""
        self.status_label.config(
            text=f"Executing: {command[:30]}...",
            fg='#00ff88'
        )

        # Run command in background
        threading.Thread(
            target=self.run_text_command,
            args=(command,),
            daemon=True
        ).start()

    def send_text_command(self, event=None):
        """Send text command to Kaya"""
        command = self.command_entry.get().strip()
        if not command:
            return

        self.status_label.config(
            text=f"Executing: {command[:30]}...",
            fg='#00ff88'
        )

        # Clear entry
        self.command_entry.delete(0, tk.END)

        # Run command in background
        threading.Thread(
            target=self.run_text_command,
            args=(command,),
            daemon=True
        ).start()

    def run_text_command(self, command):
        """Run text command via CLI"""
        try:
            # Run kaya CLI
            project_root = os.path.dirname(__file__)
            python_path = os.path.join(project_root, 'venv', 'bin', 'python')
            cli_path = os.path.join(project_root, 'agent_system', 'cli.py')

            result = subprocess.run(
                [python_path, cli_path, 'kaya', command],
                cwd=project_root,
                env={**os.environ, 'PYTHONPATH': project_root},
                capture_output=True,
                text=True,
                timeout=120
            )

            # Update status
            if result.returncode == 0:
                # Parse result for user-friendly message
                if 'Success: True' in result.stdout:
                    self.root.after(0, lambda: self.status_label.config(
                        text="✅ Command completed!",
                        fg='#00ff88'
                    ))
                else:
                    self.root.after(0, lambda: self.status_label.config(
                        text="⚠️ Check console for details",
                        fg='#ffaa00'
                    ))
            else:
                self.root.after(0, lambda: self.status_label.config(
                    text="❌ Command failed",
                    fg='#ff4444'
                ))

            # Print output to console
            print("\n" + "="*60)
            print(f"Command: {command}")
            print("="*60)
            print(result.stdout)
            if result.stderr:
                print("Errors:", result.stderr)
            print("="*60 + "\n")

        except Exception as e:
            print(f"Command error: {e}")
            self.root.after(0, lambda: self.status_label.config(
                text=f"Error: {str(e)}",
                fg='#ff4444'
            ))

    def run(self):
        """Start the GUI"""
        self.root.mainloop()


def main():
    """Main entry point"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                  Kaya Quick Access GUI                       ║
╚══════════════════════════════════════════════════════════════╝

Keyboard Shortcuts:
  Ctrl+Shift+E  - Execute Mission
  Ctrl+Shift+F  - Fix All Tests
  Enter         - Send text command
  Escape        - Close window

Quick Buttons:
  🚀 Execute Mission   - Start full mission orchestration
  Fix All Tests        - Iterative test fixing
  Status               - Check current status

Commands you can type:
  - "execute the mission"
  - "fix all test failures"
  - "use opus for everything"
  - "use sonnet for scribe"
  - "status"

The window will stay in the top-right corner.
Watch http://localhost:8080 for real-time agent activity!
    """)

    app = KayaQuickAccess()
    app.run()


if __name__ == '__main__':
    main()
