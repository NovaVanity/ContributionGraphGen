import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from datetime import datetime, timedelta
import subprocess
import json
import os
import shutil
import sys
import socket
import random

INTENSITY_LEVELS = 5
WEEKS = 52
DAYS = 7
SETTINGS_FILE = 'settings.json'
SAVES_FOLDER = 'saves'

INTENSITY_TO_COMMITS = {
    0: 0,    # No contributions
    1: 2,    # 1-3 contributions (using 2 as middle ground)
    2: 6,    # 4-9 contributions (using 6 as middle ground)
    3: 15,   # 10-19 contributions (using 15 as middle ground)
    4: 25    # 20+ contributions (using 25 as reasonable maximum)
}

LIGHT_COLORS = ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39']  # GitHub light theme colors
DARK_COLORS = ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353']   # GitHub dark theme colors
DEFAULT_THEME = 'dark'

THEME_COLORS = {
    'light': {
        'bg': '#ffffff',
        'fg': '#000000',
        'button_bg': '#e0e0e0',
        'button_fg': '#000000',
        'button_active_bg': '#d0d0d0',
        'button_active_fg': '#000000',
        'menu_bg': '#f0f0f0',
        'menu_fg': '#000000',
        'menu_active_bg': '#e0e0e0',
        'menu_active_fg': '#000000'
    },
    'dark': {
        'bg': '#1e1e1e',
        'fg': '#ffffff',
        'button_bg': '#2c2c2c',
        'button_fg': '#ffffff',
        'button_active_bg': '#404040',
        'button_active_fg': '#ffffff',
        'menu_bg': '#2c2c2c',
        'menu_fg': '#ffffff',
        'menu_active_bg': '#404040',
        'menu_active_fg': '#ffffff'
    }
}


def check_instance():
    """Ensure that only one instance of the application is running."""
    try:
        instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        instance_socket.bind(('localhost', 47200))
        instance_socket.listen(1)
        return instance_socket
    except socket.error:
        messagebox.showerror(
            "Instance Already Running",
            "Another instance of the application is already running.\nPlease close it first."
        )
        sys.exit(1)


def check_dependencies():
    """Check if Git is installed."""
    if shutil.which('git') is None:
        messagebox.showerror(
            "Dependency Error",
            "Git is not installed or not found in PATH."
            "Please install Git to use this program."
        )
        sys.exit()


class LoadingScreen(tk.Toplevel):
    """A simple loading screen displayed during initialization."""

    def __init__(self, parent, theme='light'):
        super().__init__(parent)
        colors = THEME_COLORS[theme]
        self.title("Loading")
        self.geometry("300x150")
        self.resizable(False, False)
        self.configure(bg=colors['bg'])
        self.transient(parent)
        self.grab_set()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - 300) // 2
        y = (screen_height - 150) // 2
        self.geometry(f"300x150+{x}+{y}")
        self.dots = 0
        self.loading_label = tk.Label(
            self,
            text="Loading",
            font=('Helvetica', 14, 'bold'),
            fg=colors['fg'],
            bg=colors['bg']
        )
        self.loading_label.place(relx=0.5, rely=0.3, anchor='center')
        self.progress = ttk.Progressbar(
            self,
            orient="horizontal",
            length=200,
            mode="indeterminate"
        )
        self.progress.place(relx=0.5, rely=0.5, anchor='center')
        self.progress.start(10)
        self.animate_text()
        self.after(2000, self.finish)

    def animate_text(self):
        if not hasattr(self, '_destroyed'):
            self.dots = (self.dots + 1) % 4
            self.loading_label.config(text="Loading" + "." * self.dots)
            self.after(300, self.animate_text)

    def finish(self):
        self.progress.stop()
        self.destroy()

    def destroy(self):
        self._destroyed = True
        super().destroy()


class ModernButton(tk.Button):
    """A modern styled button with hover effects."""

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_gui = self.find_parent_gui(master)
        self.update_colors()
        self.bind('<Enter>', self.on_enter)
        self.bind('<Leave>', self.on_leave)

    def find_parent_gui(self, widget):
        """Find the parent GUI class instance."""
        while widget is not None:
            if isinstance(widget, CommitGridGUI):
                return widget
            widget = widget.master
        return None

    def update_colors(self):
        """Update button colors based on the current theme."""
        if self.parent_gui:
            theme = self.parent_gui.current_theme
        else:
            theme = 'light'
        colors = THEME_COLORS[theme]
        self.config(
            relief=tk.FLAT,
            bg=colors['button_bg'],
            fg=colors['button_fg'],
            activebackground=colors['button_active_bg'],
            activeforeground=colors['button_active_fg'],
            font=('Helvetica', 10),
            padx=10,
            pady=5,
            cursor='hand2'
        )

    def on_enter(self, _):
        if self.parent_gui:
            theme = self.parent_gui.current_theme
        else:
            theme = 'light'
        self.config(bg=THEME_COLORS[theme]['button_active_bg'])

    def on_leave(self, _):
        if self.parent_gui:
            theme = self.parent_gui.current_theme
        else:
            theme = 'light'
        self.config(bg=THEME_COLORS[theme]['button_bg'])


class CommitGridGUI:
    """The main GUI class for the commit grid application."""

    def __init__(self, root):
        self.root = root
        self.root.title("GitHub Contribution Graph Generator")
        self.root.configure(bg='#1e1e1e')

        self.settings = [[0 for _ in range(WEEKS)] for _ in range(DAYS)]
        self.current_theme = DEFAULT_THEME
        self.current_save = None
        self.start_date = self.get_start_date()
        self.dragging = False
        self.right_dragging = False
        self.modified_cells = set()

        self.create_loading_screen()
        self.create_menu()
        self.create_widgets()
        self.apply_theme(self.current_theme)
        self.update_title()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.resizable(False, False)
        self.center_window()

    def create_loading_screen(self):
        loading_screen = LoadingScreen(self.root, self.current_theme)
        self.root.wait_window(loading_screen)

    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'+{x}+{y}')

    def create_menu(self):
        colors = THEME_COLORS[self.current_theme]
        menubar = tk.Menu(self.root, bg=colors['menu_bg'], fg=colors['menu_fg'])
        self.root.config(menu=menubar)

        self.saves_menu = tk.Menu(menubar, tearoff=0, bg=colors['menu_bg'], fg=colors['menu_fg'],
                                  activebackground=colors['menu_active_bg'],
                                  activeforeground=colors['menu_active_fg'])
        menubar.add_cascade(label="Saves", menu=self.saves_menu)

        settings_menu = tk.Menu(menubar, tearoff=0, bg=colors['menu_bg'], fg=colors['menu_fg'],
                                activebackground=colors['menu_active_bg'],
                                activeforeground=colors['menu_active_fg'])
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Change Remote Repository", command=self.change_remote_repository)
        settings_menu.add_command(label="Change Branch", command=self.change_branch)
        settings_menu.add_command(label="Create New Branch", command=self.create_new_branch)
        settings_menu.add_separator()
        settings_menu.add_command(label="Toggle Dark/Light Mode", command=self.toggle_theme)

        self.reload_saves_menu()

    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg='#1e1e1e', padx=20, pady=20)
        main_frame.grid(row=0, column=0)
        grid_frame = tk.Frame(main_frame, bg='#1e1e1e')
        grid_frame.grid(row=0, column=0, pady=(0, 20))
        self.cells = []
        for day in range(DAYS):
            row = []
            for week in range(WEEKS):
                btn = tk.Button(
                    grid_frame,
                    width=2,
                    height=1,
                    relief=tk.FLAT,
                    borderwidth=1,
                    command=lambda d=day, w=week: self.on_cell_click(d, w)
                )
                btn.grid(row=day, column=week, padx=1, pady=1)
                btn.bind("<ButtonPress-1>", self.on_button_press)
                btn.bind("<B1-Motion>", self.on_mouse_drag)
                btn.bind("<ButtonRelease-1>", self.on_button_release)
                btn.bind("<ButtonPress-3>", self.on_right_button_press)
                btn.bind("<B3-Motion>", self.on_right_mouse_drag)
                btn.bind("<ButtonRelease-3>", self.on_right_button_release)
                row.append(btn)
            self.cells.append(row)
        control_frame = tk.Frame(main_frame, bg='#1e1e1e')
        control_frame.grid(row=1, column=0, pady=(0, 10))
        generate_btn = ModernButton(
            control_frame,
            text="Generate Commits",
            command=self.generate_commits
        )
        generate_btn.pack(side=tk.LEFT, padx=5)
        randomize_btn = ModernButton(
            control_frame,
            text="Randomize",
            command=self.randomize_commits
        )
        randomize_btn.pack(side=tk.LEFT, padx=5)
        quit_btn = ModernButton(
            control_frame,
            text="Quit",
            command=self.root.quit
        )
        quit_btn.pack(side=tk.LEFT, padx=5)

    def update_title(self):
        repo = self.get_current_repo() or "No Repo"
        branch = self.get_current_branch() or "No Branch"
        save_info = f" - Save: {self.current_save}" if self.current_save else ""
        self.root.title(f"GitHub Contribution Graph Generator - {repo} [{branch}]{save_info}")

    def on_cell_click(self, day, week):
        intensity = (self.settings[day][week] + 1) % INTENSITY_LEVELS
        self.settings[day][week] = intensity
        self.update_cell_color(day, week)

    def on_button_press(self, event):
        self.dragging = True
        self.modified_cells = set()
        widget = event.widget
        position = self.get_cell_position(widget)
        if position:
            day, week = position
            self.on_cell_click(day, week)
            self.modified_cells.add((day, week))

    def on_mouse_drag(self, event):
        if not self.dragging:
            return
        widget = event.widget.winfo_containing(event.x_root, event.y_root)
        position = self.get_cell_position(widget)
        if position and position not in self.modified_cells:
            day, week = position
            self.on_cell_click(day, week)
            self.modified_cells.add(position)

    def on_button_release(self, _):
        self.dragging = False
        self.modified_cells = set()

    def get_cell_position(self, widget):
        for day in range(DAYS):
            for week in range(WEEKS):
                if self.cells[day][week] == widget:
                    return day, week
        return None

    def update_cell_color(self, day, week):
        intensity = self.settings[day][week]
        color = self.get_color(intensity)
        self.cells[day][week].configure(bg=color)

    def apply_theme(self, theme):
        self.current_theme = theme
        colors = THEME_COLORS[theme]

        def update_widget_colors(widget):
            if isinstance(widget, tk.Frame):
                widget.configure(bg=colors['bg'])
            elif isinstance(widget, ModernButton):
                widget.update_colors()
            for child in widget.winfo_children():
                update_widget_colors(child)

        self.root.configure(bg=colors['bg'])
        update_widget_colors(self.root)
        self.saves_menu.config(
            bg=colors['menu_bg'],
            fg=colors['menu_fg'],
            activebackground=colors['menu_active_bg'],
            activeforeground=colors['menu_active_fg']
        )
        self.save_settings()

    def toggle_theme(self):
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.apply_theme(self.current_theme)

    def get_color(self, intensity):
        if intensity == 0:
            return '#f0f0f0'
        colors = DARK_COLORS if self.current_theme == 'dark' else LIGHT_COLORS
        return colors[intensity]

    def generate_commits(self):
        check_dependencies()
        self.initialize_git_repo()
        self.update_title()
        success = True
        try:
            for week in range(WEEKS):
                for day in range(DAYS):
                    num_commits = self.settings[day][week]
                    if num_commits > 0:
                        commit_date = self.get_commit_date(self.start_date, week, day)
                        self.create_commits_for_date(num_commits, commit_date)
            if self.push_to_remote():
                messagebox.showinfo("Success", "Commits generated and pushed to remote repository.")
            else:
                success = False
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"An error occurred during Git operations: {e}")
            success = False
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
            success = False
        finally:
            if not success:
                messagebox.showwarning("Operation Incomplete", "Commits were not successfully generated or pushed.")

    def randomize_commits(self):
        weights = [0.5, 0.3, 0.15, 0.05]
        intensities = [1, 2, 3, 4]
        for day in range(DAYS):
            for week in range(WEEKS):
                intensity = random.choices(intensities, weights=weights)[0]
                self.settings[day][week] = intensity
                self.update_cell_color(day, week)

    def new_save(self):
        saves = self.get_saves_list()
        if len(saves) >= 5:
            replace_save = simpledialog.askstring(
                "Replace Save",
                "Maximum saves reached (5). Choose a save to replace:\n" +
                '\n'.join(saves) + "\n\nEnter save name to replace:"
            )
            if not replace_save:
                return
            if replace_save not in saves:
                messagebox.showerror("Error", "Invalid save name.")
                return
        save_name = simpledialog.askstring("New Save", "Enter a name for the new save:")
        if save_name:
            if save_name in saves:
                if messagebox.askyesno("Save exists", "Save already exists. Do you want to override it?"):
                    self.current_save = save_name
                else:
                    return
            self.current_save = save_name
            if not os.path.exists(SAVES_FOLDER):
                os.makedirs(SAVES_FOLDER)
            self.save_settings()
            messagebox.showinfo("Save Created", f"Save '{save_name}' has been created.")
            self.update_title()
            self.reload_saves_menu()

    def load_save(self):
        saves = self.get_saves_list()
        if not saves:
            messagebox.showinfo("No Saves", "No saves available.")
            return
        save_name = simpledialog.askstring(
            "Load Save",
            "Available saves:\n" + '\n'.join(saves) + "\n\nEnter the save name to load:"
        )
        if save_name:
            if save_name in saves:
                self.load_settings(save_name)
                for day in range(DAYS):
                    for week in range(WEEKS):
                        self.update_cell_color(day, week)
                self.current_save = save_name
                self.update_title()
                self.reload_saves_menu()
                messagebox.showinfo("Save Loaded", f"Save '{save_name}' has been loaded.")
            else:
                messagebox.showerror("Load Error", "Save not found.")

    def get_saves_list(self):
        if not os.path.exists(SAVES_FOLDER):
            return []
        files = os.listdir(SAVES_FOLDER)
        saves = [os.path.splitext(f)[0] for f in files if f.endswith('.json')]
        return saves

    def reload_saves_menu(self):
        saves = self.get_saves_list()
        self.saves_menu.delete(0, tk.END)
        self.saves_menu.add_command(label="New Save", command=self.new_save)
        self.saves_menu.add_command(label="Load Save", command=self.load_save)
        if saves:
            self.saves_menu.add_separator()
            self.saves_menu.add_command(label="Current Saves:", state="disabled")
            for save in saves:
                if save == self.current_save:
                    self.saves_menu.add_command(label=f"► {save}", state="disabled")
                else:
                    self.saves_menu.add_command(label=f"   {save}", state="disabled")

    def on_right_click(self, day, week):
        self.settings[day][week] = 0
        self.update_cell_color(day, week)

    def on_right_button_press(self, event):
        self.right_dragging = True
        self.modified_cells = set()
        widget = event.widget
        position = self.get_cell_position(widget)
        if position:
            day, week = position
            self.on_right_click(day, week)
            self.modified_cells.add((day, week))

    def on_right_mouse_drag(self, event):
        if not self.right_dragging:
            return
        widget = event.widget.winfo_containing(event.x_root, event.y_root)
        position = self.get_cell_position(widget)
        if position and position not in self.modified_cells:
            day, week = position
            self.on_right_click(day, week)
            self.modified_cells.add(position)

    def on_right_button_release(self, _):
        self.right_dragging = False
        self.modified_cells = set()

    def on_closing(self):
        self.save_settings()
        if hasattr(self.root, '_socket'):
            self.root._socket.close()
        self.root.quit()

    def save_settings(self):
        data = {
            'settings': self.settings,
            'theme': self.current_theme
        }
        filename = SETTINGS_FILE if self.current_save is None else os.path.join(SAVES_FOLDER, f"{self.current_save}.json")
        try:
            with open(filename, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            messagebox.showerror("Error Saving Settings", str(e))

    def load_settings(self, save_name=None):
        if save_name is not None and os.path.exists(os.path.join(SAVES_FOLDER, f"{save_name}.json")):
            try:
                with open(os.path.join(SAVES_FOLDER, f"{save_name}.json"), 'r') as f:
                    data = json.load(f)
                self.settings = data.get('settings', [[0 for _ in range(WEEKS)] for _ in range(DAYS)])
                self.current_theme = data.get('theme', DEFAULT_THEME)
                self.apply_theme(self.current_theme)
            except Exception as e:
                messagebox.showerror("Error Loading Settings", str(e))
        else:
            self.settings = [[0 for _ in range(WEEKS)] for _ in range(DAYS)]
            self.current_theme = DEFAULT_THEME

    def initialize_git_repo(self):
        if not os.path.exists('.git'):
            subprocess.run(["git", "init"], check=True)
            subprocess.run(["git", "checkout", "-b", "main"], check=True)
            self.set_remote_repository()
            # Create or update .gitignore
            with open('.gitignore', 'w') as f:
                f.write('main.py\nsettings.json\nsaves/\n*.json\n')
        else:
            self.check_remote_repository()
            current_branch = self.get_current_branch()
            if not current_branch:
                subprocess.run(["git", "checkout", "-b", "main"], check=True)
        subprocess.run(["git", "fetch"], check=True)

    def set_remote_repository(self):
        while True:
            remote_url = simpledialog.askstring(
                "Remote Repository",
                "Enter the remote repository URL (e.g., https://github.com/username/repo.git):"
            )
            if remote_url:
                try:
                    subprocess.run(["git", "remote", "add", "origin", remote_url], check=True)
                    break
                except subprocess.CalledProcessError:
                    retry = messagebox.askretrycancel(
                        "Invalid URL",
                        "Failed to add remote repository. Please enter a valid URL."
                    )
                    if not retry:
                        break
            else:
                messagebox.showwarning(
                    "No URL Provided",
                    "A remote repository is required to push commits. Please provide a valid URL."
                )
                break

    def check_remote_repository(self):
        remotes = subprocess.run(
            ["git", "remote"],
            stdout=subprocess.PIPE,
            text=True
        ).stdout.strip()
        if 'origin' not in remotes:
            self.set_remote_repository()

    def change_remote_repository(self):
        current_repo = self.get_current_repo()
        remote_url = simpledialog.askstring(
            "Change Remote Repository",
            "Current repository: {}\nEnter new repository URL:".format(current_repo or "None")
        )
        if remote_url:
            try:
                if current_repo:
                    subprocess.run(["git", "remote", "remove", "origin"], check=True)
                subprocess.run(["git", "remote", "add", "origin", remote_url], check=True)
                self.update_title()
            except subprocess.CalledProcessError:
                messagebox.showerror("Remote Error", "Failed to change remote repository.")

    def create_new_branch(self):
        branch = simpledialog.askstring("Create New Branch", "Enter the name of the new branch:")
        if branch:
            try:
                subprocess.run(["git", "checkout", "-b", branch], check=True)
                self.update_title()
            except subprocess.CalledProcessError:
                messagebox.showerror("Branch Error", f"Failed to create and switch to branch '{branch}'.")

    def change_branch(self):
        branches = subprocess.run(
            ["git", "branch"],
            stdout=subprocess.PIPE,
            text=True,
            check=True
        ).stdout.strip().split('\n')
        branches = [b.strip().replace('* ', '') for b in branches]
        branch = simpledialog.askstring(
            "Change Branch",
            "Available branches:\n" + '\n'.join(branches) + "\n\nEnter the branch to switch to:"
        )
        if branch:
            try:
                subprocess.run(["git", "checkout", branch], check=True)
                self.update_title()
            except subprocess.CalledProcessError:
                messagebox.showerror("Branch Error", f"Failed to switch to branch '{branch}'.")

    def push_to_remote(self):
        current_branch = self.get_current_branch()
        if current_branch is None:
            messagebox.showerror("Error", "No current branch found.")
            return False
        try:
            # Fetch the latest commits from the remote repository
            subprocess.run(["git", "fetch"], check=True)
            # Rebase local commits on top of the fetched commits
            subprocess.run(["git", "rebase", f"origin/{current_branch}"], check=False)
            # Push and set upstream if it's the first push
            subprocess.run(["git", "push", "--set-upstream", "origin", current_branch], check=True)
            return True
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Push Error", f"Failed to push to remote repository:\n{e}")
            return False

    @staticmethod
    def get_current_branch():
        try:
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stdout=subprocess.PIPE,
                text=True,
                check=True
            ).stdout.strip()
            return branch
        except subprocess.CalledProcessError:
            return None

    @staticmethod
    def get_current_repo():
        try:
            repo = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                stdout=subprocess.PIPE,
                text=True,
                check=True
            ).stdout.strip()
            return repo
        except subprocess.CalledProcessError:
            return None

    def create_commit(self, date, commit_number):
        date_str = date.strftime("%a %b %d %H:%M:%S %Y %z")
        with open("commit.txt", "a") as f:
            f.write(f"Commit #{commit_number} on {date_str}\n")
        subprocess.run(["git", "add", "commit.txt"], check=True)
        subprocess.run([
            "git", "commit", "-m", f"Commit #{commit_number} on {date_str}",
            "--date", date_str
        ], check=True)

    def create_commits_for_date(self, intensity_level, date):
        num_commits = INTENSITY_TO_COMMITS[intensity_level]
        for i in range(num_commits):
            # Spread commits throughout the day between 9 AM and 5 PM
            total_seconds = 8 * 3600  # 8 hours
            seconds_per_commit = total_seconds / num_commits if num_commits > 0 else 0
            commit_time = date.replace(hour=9, minute=0, second=0) + timedelta(seconds=i * seconds_per_commit)
            self.create_commit(commit_time, commit_number=i + 1)

    @staticmethod
    def get_start_date():
        today = datetime.now()
        # GitHub contribution graph grids start on Sunday
        weekday = (today.weekday() + 1) % 7  # Adjust so that Sunday=0
        last_sunday = today - timedelta(days=weekday)
        last_sunday = last_sunday.replace(hour=12, minute=0, second=0, microsecond=0)
        start_date = last_sunday - timedelta(weeks=WEEKS - 1)
        return start_date

    @staticmethod
    def get_commit_date(start_date, week, day):
        return start_date + timedelta(weeks=week, days=day)


def main():
    socket_inst = check_instance()
    root = tk.Tk()
    root._socket = socket_inst
    app = CommitGridGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()