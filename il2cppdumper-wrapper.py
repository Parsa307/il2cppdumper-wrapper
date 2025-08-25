import customtkinter as ctk
import subprocess
import os
import shutil
import threading

# Set up a cool dark theme for the app!
ctk.set_appearance_mode("System")  # Options: "Light", "Dark", "System"
ctk.set_default_color_theme("blue")  # Options: "blue", "green", "dark-blue"

# --- Helper function for native file/directory selection ---
def get_native_dialog_selection(prompt, file_type="file", initial_dir=None):
    """
    Attempts to use zenity or kdialog for native file/directory selection on Linux.
    Returns a tuple: (selected_path, status_code)
    selected_path: string if selected, None otherwise.
    status_code:
        0 = Success (path selected)
        1 = User cancelled
        -1 = Dialog tool not found or execution failed.
    """
    if os.name != 'posix':
        # Not on a Linux/Unix-like system, native dialogs won't work.
        # Since we have no fallbacks, this means no dialog can be opened.
        return (None, -1)

    command = []

    tool_found = False
    if shutil.which("zenity"):
        tool_found = True
        command = ["zenity", "--file-selection", "--title", prompt]
        if file_type == "directory":
            command.append("--directory")
        if initial_dir:
            # Zenity needs a trailing slash for initial directory to show its contents
            command.extend(["--filename", os.path.join(initial_dir, '')])

    # If Zenity not found, try Kdialog (Qt/KDE-based)
    elif shutil.which("kdialog"):
        tool_found = True
        command = ["kdialog", "--title", prompt]
        if file_type == "directory":
            command.append("--getexistingdirectory")
        else: # file_type == "file"
            command.append("--getopenfilename")
        if initial_dir:
            command.append(initial_dir)

    if not tool_found:
        return (None, -1) # No native dialog tool found

    if command:
        try:
            # Run the command and capture its output
            # check=False is crucial here so subprocess doesn't raise an error on non-zero exit codes (like user cancelling)
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            selected_path = result.stdout.strip()

            if result.returncode == 0 and selected_path:
                return (selected_path, 0) # Success, path selected
            elif result.returncode == 1: # Common exit code for user cancel in zenity/kdialog
                return (None, 1) # User cancelled
            else:
                # Some other non-zero exit code or empty path for an unexpected failure
                # This could happen if the dialog itself failed for some reason other than cancel
                return (None, -1)
        except Exception as e:
            # Catch any other unexpected errors during subprocess execution
            print(f"Error running native dialog command '{' '.join(command)}': {e}") # For debugging
            return (None, -1)

    # This point should ideally not be reached if tool_found is True and command is built
    return (None, -1)


class IL2CppDumperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Needed to avoid Hyprland issues & other issues
        ctk.set_widget_scaling(1.0)
        ctk.set_window_scaling(1.0)

        # Initialize the Program
        self.title("IL2CppDumper GUI Wrapper")
        self.geometry("700x400")

        # Configure grid for responsive layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1) # Make the output log expandable

        # --- Input Fields ---

        # Executable File Input
        self.exec_label = ctk.CTkLabel(self, text="Executable File:")
        self.exec_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.exec_entry = ctk.CTkEntry(self, width=400, placeholder_text="Path to your executable file (e.g., GameAssembly.dll)")
        self.exec_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.exec_button = ctk.CTkButton(self, text="Browse", command=self.browse_executable)
        self.exec_button.grid(row=0, column=2, padx=10, pady=10)

        # Global Metadata File Input
        self.meta_label = ctk.CTkLabel(self, text="Global Metadata File:")
        self.meta_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.meta_entry = ctk.CTkEntry(self, width=400, placeholder_text="Path to your global-metadata.dat file")
        self.meta_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.meta_button = ctk.CTkButton(self, text="Browse", command=self.browse_metadata)
        self.meta_button.grid(row=1, column=2, padx=10, pady=10)

        # Output Directory Input
        self.output_label = ctk.CTkLabel(self, text="Output Directory:")
        self.output_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.output_entry = ctk.CTkEntry(self, width=400, placeholder_text="Directory to save the dumped files")
        self.output_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        self.output_button = ctk.CTkButton(self, text="Browse", command=self.browse_output_dir)
        self.output_button.grid(row=2, column=2, padx=10, pady=10)

        # --- Run Button ---
        self.run_button = ctk.CTkButton(self, text="Run IL2CppDumper", command=self.run_dumper, fg_color="green", hover_color="darkgreen")
        self.run_button.grid(row=3, column=0, columnspan=3, padx=10, pady=20)

        # --- Output Log ---
        self.log_label = ctk.CTkLabel(self, text="Command Output:")
        self.log_label.grid(row=4, column=0, padx=10, pady=(10, 0), sticky="nw")
        self.output_log = ctk.CTkTextbox(self, width=600, height=150, wrap="word")
        self.output_log.grid(row=4, column=1, columnspan=2, padx=10, pady=(10, 10), sticky="nsew")

        # Configure tags for colored text in the log for better readability
        self.output_log.tag_config("red", foreground="#FF6B6B") # Lighter red for errors
        self.output_log.tag_config("green", foreground="#6BFF6B") # Lighter green for success
        self.output_log.tag_config("blue", foreground="#6B6BFF") # Lighter blue for system messages/info
        self.output_log.tag_config("info", foreground="#BBBBBB") # Grey for general command output
        self.output_log.tag_config("warning", foreground="#FFD700") # Gold for warnings

    # Helper function to log messages to the textbox with optional colors
    def _log_message(self, message, tag=None):
        self.output_log.configure(state="normal") # Enable logging
        self.output_log.insert("end", message + "\n", tag)
        self.output_log.see("end") # Scroll to the end of the log
        self.output_log.configure(state="disabled") # Disable logging again

    # Function to browse for the executable file using the new native dialog helper
    def browse_executable(self):
        file_path, status = get_native_dialog_selection(
            prompt="Select Executable File",
        )
        if status == 0: # Success, path selected
            self.exec_entry.delete(0, ctk.END)
            self.exec_entry.insert(0, file_path)
            self._log_message(f"Selected executable: {file_path}", "info")
        elif status == -1: # Tool not found or failed to execute
            self._log_message("Error: Could not open a native file dialog. Please ensure 'zenity' or 'kdialog' is installed and working.", "red")
        # If status is 1 (user cancelled), we do nothing, which is the desired behavior.

    # Function to browse for the global-metadata.dat file using the new native dialog helper
    def browse_metadata(self):
        file_path, status = get_native_dialog_selection(
            prompt="Select Global Metadata File",
        )
        if status == 0: # Success, path selected
            self.meta_entry.delete(0, ctk.END)
            self.meta_entry.insert(0, file_path)
            self._log_message(f"Selected metadata: {file_path}", "info")
        elif status == -1: # Tool not found or failed to execute
            self._log_message("Error: Could not open a native file dialog. Please ensure 'zenity' or 'kdialog' is installed and working.", "red")

    # Function to browse for the output directory using the new native dialog helper
    def browse_output_dir(self):
        dir_path, status = get_native_dialog_selection(
            prompt="Select Output Directory",
            file_type="directory"
        )
        if status == 0: # Success, path selected
            self.output_entry.delete(0, ctk.END)
            self.output_entry.insert(0, dir_path)
            self._log_message(f"Selected output directory: {dir_path}", "info")
        elif status == -1: # Tool not found or failed to execute
            self._log_message("Error: Could not open a native directory dialog. Please ensure 'zenity' or 'kdialog' is installed and working.", "red")

    # --- Asynchronous Logic ---
    def run_dumper_async(self):
        """
        The heavy-lifting function that runs the subprocess in a new thread.
        All GUI updates must be done with self.after() to be thread-safe.
        """
        exec_file = self.exec_entry.get()
        meta_file = self.meta_entry.get()
        output_dir = self.output_entry.get()

        # Basic validation (done on main thread before starting the thread)
        # This part is a backup, as the main run_dumper() does the initial check.
        if not all([exec_file, meta_file, output_dir]):
            self.after(0, self._log_message, "Internal Error: Fields were not validated.", "red")
            return

        # Check and create output directory
        if not os.path.isdir(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
                self.after(0, self._log_message, f"Warning: Output directory doesn't exist, creating output directory: {output_dir}", "warning")
            except OSError as e:
                self.after(0, self._log_message, f"Error: creating output directory '{output_dir}': {e}", "red")
                self.after(0, self.run_button.configure, {"state": "normal"})
                return

        command = ["il2cppdumper", exec_file, meta_file, output_dir]
        self.after(0, self._log_message, f"Preparing to run: `{' '.join(command)}`", "blue")

        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False
            )

            if process.stdout:
                self.after(0, self._log_message, process.stdout, "info")
            if process.stderr:
                self.after(0, self._log_message, f"Error: (stderr): {process.stderr}", "red")

            if process.returncode == 0:
                self.after(0, self._log_message, "Command completed successfully! ✨", "green")
            else:
                self.after(0, self._log_message, f"Command failed with exit code {process.returncode}", "red")

        except FileNotFoundError:
            self.after(0, self._log_message, "Error: 'il2cppdumper' command not found. Please ensure it's installed and in your system's PATH.", "red")
        except Exception as e:
            self.after(0, self._log_message, f"An unexpected error occurred: {e}", "red")
        finally:
            self.after(0, lambda: self.run_button.configure(state="normal"))

    def run_dumper(self):
        """
        The main handler for the 'Run' button.
        It performs quick validation and starts the asynchronous process.
        """
        exec_file = self.exec_entry.get()
        meta_file = self.meta_entry.get()
        output_dir = self.output_entry.get()

        # Perform initial, quick validation on the main thread
        if not all([exec_file, meta_file, output_dir]):
            self._log_message("Error: All fields must be filled!", "red")
            return
        if not os.path.exists(exec_file):
            self._log_message(f"Error: Executable file not found at '{exec_file}'", "red")
            return
        if not os.path.exists(meta_file):
            self._log_message(f"Error: Metadata file not found at '{meta_file}'", "red")
            return

        # Disable button to prevent multiple concurrent runs
        self.run_button.configure(state="disabled")

        # Clear the output log
        self.output_log.configure(state="normal")
        self.output_log.delete("1.0", ctk.END)
        self.output_log.configure(state="disabled")

        # Start the dumper in a new thread
        dumper_thread = threading.Thread(target=self.run_dumper_async)
        dumper_thread.start()

if __name__ == "__main__":
    app = IL2CppDumperApp()
    app.mainloop()
