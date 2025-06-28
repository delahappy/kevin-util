import csv
import os
import sys
import platform
import psutil
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk  # For handling images
import json
import threading
import re

APP_VERSION = "1.5.1.c"

def big_search_csv():
    # Logging setup
    logging.basicConfig(
        filename='big_search_csv.log',
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logging.info("Application started.")

    root = tk.Tk()
    root.withdraw()  # Hide main window for splash

    # ----------- SPLASH / LOADING SCREEN -----------
    splash = tk.Toplevel()
    splash.title("Loading...")
    splash.overrideredirect(True)  # No window border
    splash.geometry("400x300+500+250")
    splash.lift()

    def resource_path(relative_path):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
        return os.path.join(base_path, relative_path)

    splash_img_path = resource_path('loading.png')
    if os.path.exists(splash_img_path):
        img = Image.open(splash_img_path)
        img = img.resize((400, 300), Image.LANCZOS)
        splash_img = ImageTk.PhotoImage(img)
        lbl = tk.Label(splash, image=splash_img)
        lbl.image = splash_img
        lbl.pack(fill="both", expand=True)
    else:
        lbl = tk.Label(splash, text="Loading Big Search...", font=("Arial", 20))
        lbl.pack(expand=True, fill="both")

    # Center splash
    splash.update_idletasks()
    w = splash.winfo_screenwidth()
    h = splash.winfo_screenheight()
    size = tuple(int(_) for _ in splash.geometry().split('+')[0].split('x'))
    splash.geometry("%dx%d+%d+%d" % (size + ((w - size[0]) // 2, (h - size[1]) // 2)))

    # Main vars
    settings_file = "settings.json"
    root.persistent_file_enabled = tk.BooleanVar(value=False)
    root.persistent_file_path = None
    root.ready_for_search = False
    root.file_loaded = False
    root.header = []
    root.data = []
    root.search_delay = 300
    root.live_search_enabled = True
    root.auto_paste_enabled = tk.BooleanVar(value=True)
    clipboard_history = []

    def load_settings():
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r") as f:
                    settings = json.load(f)
                    root.persistent_file_enabled.set(settings.get("persistent", False))
                    if root.persistent_file_enabled.get():
                        root.persistent_file_path = settings.get("file_path", None)
                    root.auto_paste_enabled.set(settings.get("auto_paste", True))
            except Exception as e:
                logging.warning(f"Failed to load settings: {e}")

    def save_settings():
        try:
            with open(settings_file, "w") as f:
                json.dump({
                    "persistent": root.persistent_file_enabled.get(),
                    "file_path": root.persistent_file_path,
                    "auto_paste": root.auto_paste_enabled.get()
                }, f)
        except Exception as e:
            logging.warning(f"Failed to save settings: {e}")

    # ------------- GUI SETUP (run after splash) -------------------
    def show_main_app():
        global search_after_id
        search_after_id = None
        splash.destroy()
        root.deiconify()
        root.title("Big Search CSV")
        icon_path = resource_path('icon.png')
        if os.path.exists(icon_path):
            try:
                root.iconphoto(True, tk.PhotoImage(file=icon_path))
                logging.info("Icon set successfully.")
            except Exception as e:
                logging.warning(f"Could not set window icon: {e}")
                messagebox.showwarning("Icon Error", f"Could not set window icon:\n{e}")
        else:
            logging.warning("Icon file 'icon.png' not found.")
        # ----- Styles -----
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', font=('Arial', 10))
        style.configure('TButton', font=('Arial', 10))
        style.configure('TEntry', font=('Arial', 10))
        style.configure('Treeview', font=('Arial', 10))
        style.configure('Treeview.Heading', font=('Arial', 11, 'bold'))

        # ------- Functions -------
        def load_csv_file(file_path):
            try:
                with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    header = next(reader)
                    root.header = header
                    data = list(reader)
                    root.data = data
                    logging.info(f"Loaded CSV file: {file_path}")
                    selected_columns = show_column_selector(header)
                    if not selected_columns:
                        messagebox.showinfo("No Columns Selected", "No columns were selected. Displaying all columns.")
                        selected_columns = header
                    root.selected_columns = selected_columns
                    root.col_indices = {col: idx for idx, col in enumerate(header)}
                    # --- Populate the result table with all data for selected columns ---
                    for item in result_table.get_children():
                        result_table.delete(item)
                    result_table["columns"] = selected_columns
                    result_table["show"] = "headings"
                    for idx, col_name in enumerate(selected_columns):
                        result_table.heading(col_name, text=col_name)
                        result_table.column(col_name, width=200, anchor='w')
                    col_indices = [header.index(col) for col in selected_columns]
                    # Only insert data if at least one column is selected
                    if selected_columns:
                        for row in data:
                            if any(row):
                                row_values = [row[idx] if idx < len(row) else '' for idx in col_indices]
                                if any(row_values):
                                    result_table.insert("", tk.END, values=row_values)
                    # --- Populate the town/city dropdown if present in selected columns ---
                    town_city_col = None
                    for col in selected_columns:
                        if col.lower() in ("town", "city"):
                            town_city_col = col
                            break
                    if town_city_col:
                        idx = header.index(town_city_col)
                        unique_vals = sorted(set(row[idx] for row in data if len(row) > idx and row[idx].strip()))
                        town_dropdown['values'] = ['All Towns'] + unique_vals
                        town_dropdown.current(0)
                        town_dropdown.config(state='readonly')
                        town_label.config(text=f"Select {town_city_col}:")
                        town_dropdown.bind("<<ComboboxSelected>>", lambda e: filter_by_town_city())
                    else:
                        town_dropdown['values'] = ['All Towns']
                        town_dropdown.current(0)
                        town_dropdown.config(state='disabled')
                        town_label.config(text="Column selection mode")
                        town_dropdown.unbind("<<ComboboxSelected>>")
                    if not status_lock["locked"]:
                        status_label.config(text=f"Loaded file: {file_path}")
                    root.file_loaded = True
                    root.persistent_file_path = file_path
                    root.ready_for_search = True
                    save_settings()
                    return True
            except Exception as e:
                logging.error(f"Failed to open file: {e}")
                messagebox.showerror("Error", f"Failed to open file:\n{e}")
                if not status_lock["locked"]:
                    status_label.config(text="No file loaded.")
                root.file_loaded = False
                return False

        def filter_by_town_city():
            selected = town_dropdown.get()
            selected_columns = getattr(root, 'selected_columns', root.header)
            header = root.header
            data = root.data
            # Find the first selected column that is 'town' or 'city'
            town_city_col = None
            for col in selected_columns:
                if col.lower() in ("town", "city"):
                    town_city_col = col
                    break
            if not town_city_col or selected == 'All Towns':
                # Show all data
                col_indices = [header.index(col) for col in selected_columns]
                result_table.delete(*result_table.get_children())
                for row in data:
                    if any(row):
                        row_values = [row[idx] if idx < len(row) else '' for idx in col_indices]
                        if any(row_values):
                            result_table.insert("", tk.END, values=row_values)
                return
            idx = header.index(town_city_col)
            col_indices = [header.index(col) for col in selected_columns]
            result_table.delete(*result_table.get_children())
            for row in data:
                if len(row) > idx and row[idx] == selected:
                    row_values = [row[i] if i < len(row) else '' for i in col_indices]
                    if any(row_values):
                        result_table.insert("", tk.END, values=row_values)

        def show_column_selector(header):
            selected = set(header)
            dialog = tk.Toplevel(root)
            dialog.title("Select Columns to Display")
            dialog.geometry("400x400")
            # --- Main container ---
            container = tk.Frame(dialog)
            container.pack(fill="both", expand=True)
            # --- Scrollable frame for checkboxes ---
            canvas = tk.Canvas(container, borderwidth=0)
            frame = tk.Frame(canvas)
            vsb = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=vsb.set)
            canvas.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")
            canvas.create_window((0, 0), window=frame, anchor="nw")
            def on_frame_configure(event):
                canvas.configure(scrollregion=canvas.bbox("all"))
            frame.bind("<Configure>", on_frame_configure)
            vars = []
            for i, col in enumerate(header):
                # First 5 columns checked by default, rest unchecked
                var = tk.BooleanVar(value=(i < 5))
                cb = tk.Checkbutton(frame, text=col, variable=var)
                cb.pack(anchor='w')
                vars.append((col, var))
            # --- Button frame at the bottom, outside the scrollable area ---
            btn_frame = tk.Frame(dialog)
            btn_frame.pack(side='bottom', fill='x', pady=5)
            def on_ok():
                sel = [col for col, var in vars if var.get()]
                dialog.selected = sel
                dialog.destroy()
            btn = tk.Button(btn_frame, text="OK", command=on_ok)
            btn.pack(side='left', padx=10, pady=5)
            close_btn = tk.Button(btn_frame, text="Cancel", command=dialog.destroy)
            close_btn.pack(side='right', padx=10, pady=5)
            dialog.bind('<Return>', lambda event: on_ok())
            dialog.transient(root)
            dialog.grab_set()
            root.wait_window(dialog)
            return getattr(dialog, 'selected', header)

        def open_file():
            file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
            if file_path:
                load_csv_file(file_path)
            else:
                root.file_loaded = False
                root.ready_for_search = False

        def perform_search():
            if not root.file_loaded:
                return
            try:
                search_address = entry_address.get().strip()
                case_sensitive = var_case.get()
                matches = []
                header = root.header
                data = root.data
                selected_columns = getattr(root, 'selected_columns', header)
                # Find indices for selected columns
                col_indices = [header.index(col) for col in selected_columns]
                for row in data:
                    # Search logic: if search box is empty, show all rows
                    if search_address:
                        row_text = ' '.join(row[idx] for idx in col_indices if idx < len(row))
                        if not case_sensitive:
                            match = search_address.lower() in row_text.lower()
                        else:
                            match = search_address in row_text
                        if not match:
                            continue
                    matches.append(row)
                for item in result_table.get_children():
                    result_table.delete(item)
                if matches:
                    result_table["columns"] = selected_columns
                    result_table["show"] = "headings"
                    for idx, col_name in enumerate(selected_columns):
                        result_table.heading(col_name, text=col_name)
                        result_table.column(col_name, width=200, anchor='w')
                    for row in matches:
                        row_values = [row[idx] if idx < len(row) else '' for idx in col_indices]
                        result_table.insert("", tk.END, values=row_values)
                    if not status_lock["locked"]:
                        status_label.config(text=f"Found {len(matches)} matching records.")
                    logging.info(f"Search performed. Found {len(matches)} matching records.")
                else:
                    if not status_lock["locked"]:
                        status_label.config(text="No matches found.")
                    logging.info("Search performed. No matches found.")
            except Exception as e:
                logging.error(f"Error during search: {e}")
                messagebox.showerror("Error", f"An error occurred during search:\n{e}")

        def trigger_search(*args):
            global search_after_id
            if root.live_search_enabled:
                if search_after_id:
                    root.after_cancel(search_after_id)
                if var_search_delay_enabled.get():
                    delay = root.search_delay
                else:
                    delay = 0
                search_after_id = root.after(delay, perform_search)

        def manual_search():
            perform_search()

        def copy_selected():
            try:
                selected_items = result_table.selection()
                if not selected_items:
                    messagebox.showinfo("No Selection", "Please select a row to copy.")
                    return
                copied_text = ''
                for item in selected_items:
                    row_values = result_table.item(item)['values']
                    copied_text += '\t'.join(str(value) for value in row_values) + '\n'
                root.clipboard_clear()
                root.clipboard_append(copied_text)
                root.bell()
                show_temp_status("Copied selected rows!", 1500)
                logging.info("Selected rows copied to clipboard.")
            except Exception as e:
                logging.error(f"Error copying selected rows: {e}")
                messagebox.showerror("Error", f"An error occurred while copying:\n{e}")

        def exit_app():
            logging.info("Application exited.")
            root.quit()

        def show_about():
            about_window = tk.Toplevel(root)
            about_window.title("About Big Search CSV")
            about_window.resizable(True, True)
            bg_image_path = resource_path('about_bg.png')
            if os.path.exists(bg_image_path):
                bg_image = Image.open(bg_image_path)
            else:
                messagebox.showwarning("Image Not Found", "Background image 'about_bg.png' not found.")
                bg_image = None
            canvas = tk.Canvas(about_window)
            canvas.pack(fill='both', expand=True)
            def resize_image(event):
                canvas_width = event.width
                canvas_height = event.height
                if bg_image:
                    resized = bg_image.resize((canvas_width, canvas_height), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(resized)
                    canvas.photo = photo
                    canvas.create_image(0, 0, image=photo, anchor='nw')
                canvas.create_rectangle(0, 0, canvas_width, canvas_height, fill='black', stipple='gray25')
                canvas.delete('text')
                text_content = (
                    f"Big Search CSV\n"
                    f"Version {APP_VERSION}\n\n"
                    "Created by OpenAI's ChatGPT (v4),\n"
                    "guided by Kevin Bryant, to deliver exactly the features needed.\n\n"
                    "System Information:\n"
                )
                system_info = platform.uname()
                os_info = f"{system_info.system} {system_info.release} ({system_info.version})"
                processor_info = system_info.processor or platform.processor()
                machine_info = system_info.machine
                python_version = sys.version.split()[0]
                cpu_usage = psutil.cpu_percent(interval=1)
                total_memory = psutil.virtual_memory().total / (1024 ** 3)
                available_memory = psutil.virtual_memory().available / (1024 ** 3)
                memory_usage = psutil.virtual_memory().percent
                total_disk = psutil.disk_usage('/').total / (1024 ** 3)
                disk_usage = psutil.disk_usage('/').percent
                sys_info_text = (
                    f"Operating System: {os_info}\n"
                    f"Machine Type: {machine_info}\n"
                    f"Processor: {processor_info}\n"
                    f"Python Version: {python_version}\n"
                    f"CPU Usage: {cpu_usage}%\n"
                    f"Total Memory: {total_memory:.2f} GB\n"
                    f"Available Memory: {available_memory:.2f} GB\n"
                    f"Memory Usage: {memory_usage}%\n"
                    f"Total Disk Space: {total_disk:.2f} GB\n"
                    f"Disk Usage: {disk_usage}%\n"
                )
                full_text = text_content + sys_info_text
                canvas.create_text(
                    canvas_width // 2,
                    canvas_height // 2,
                    text=full_text,
                    fill="white",
                    font=("Arial", 12),
                    width=canvas_width - 40,
                    tags='text',
                    justify='center'
                )
            if bg_image:
                photo = ImageTk.PhotoImage(bg_image)
                canvas.photo = photo
                canvas.create_image(0, 0, image=photo, anchor='nw')
            about_window.bind("<Configure>", resize_image)
            about_window.transient(root)
            about_window.grab_set()
            root.wait_window(about_window)

        def show_help():
            help_window = tk.Toplevel(root)
            help_window.title("Help")
            help_window.resizable(True, True)
            help_text = (
                "Instructions:\n\n"
                "1. Open a CSV file using File > Open.\n"
                "   - The CSV file must contain the following headers: 'Address', 'Town', 'Location ID'.\n"
                "   - Headers are case-insensitive.\n"
                "2. Enter an address to search for in the 'Enter Address' field.\n"
                "3. (Optional) Select a town to filter results.\n"
                "4. View results in the table below.\n"
                "5. Double-click a row to copy the Location ID.\n"
                "6. Right-click to copy selected rows.\n\n"
                "Settings Explanation:\n\n"
                "- **Case Sensitive**: Toggles case sensitivity for searches.\n"
                "- **Enable Live Search**: Searches are performed as you type.\n"
                "- **Enable Search Delay**: Adds a delay before search is performed.\n"
                "- **Set Search Delay**: Adjust delay for live searches.\n"
                "- **Change Background Color**: Customize app color.\n"
                "- **Change Theme**: Select app theme.\n"
                "- **Auto-Paste from Clipboard on Focus**: When enabled, the search entry auto-fills with your clipboard whenever the app gains focus."
            )
            tk.Message(help_window, text=help_text, width=500).pack(padx=10, pady=10, fill='both', expand=True)
            help_window.transient(root)
            help_window.grab_set()
            root.wait_window(help_window)

        def show_clipboard_history():
            if not clipboard_history:
                messagebox.showinfo("Clipboard History", "No clipboard history available.")
                return
            history_window = tk.Toplevel(root)
            history_window.title("Clipboard History")
            history_window.geometry("400x300")
            listbox = tk.Listbox(history_window, font=("Arial", 10))
            for item in reversed(clipboard_history):
                listbox.insert(tk.END, item)
            listbox.pack(fill="both", expand=True, padx=10, pady=10)
            def reinsert_selected():
                try:
                    selected = listbox.get(listbox.curselection())
                    entry_address.delete(0, tk.END)
                    entry_address.insert(0, selected)
                    trigger_search()
                    history_window.destroy()
                except Exception:
                    pass
            tk.Button(history_window, text="Paste Selected", command=reinsert_selected).pack(pady=5)
            history_window.transient(root)
            history_window.grab_set()
            root.wait_window(history_window)

        # --- Menu ---
        menu_bar = tk.Menu(root)
        root.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Open", command=open_file)
        file_menu.add_separator()
        file_menu.add_checkbutton(
            label="Load file on startup",
            onvalue=True, offvalue=False,
            variable=root.persistent_file_enabled,
            command=save_settings
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=exit_app)
        menu_bar.add_cascade(label="File", menu=file_menu)

        options_menu = tk.Menu(menu_bar, tearoff=0)
        var_case_menu = tk.BooleanVar()
        var_case_menu.set(False)
        options_menu.add_checkbutton(label="Case Sensitive", variable=var_case_menu)
        var_case = var_case_menu
        var_case.trace_add("write", trigger_search)
        var_live_search = tk.BooleanVar()
        var_live_search.set(True)
        options_menu.add_checkbutton(label="Enable Live Search", variable=var_live_search, command=lambda: toggle_live_search())
        var_search_delay_enabled = tk.BooleanVar()
        var_search_delay_enabled.set(True)
        options_menu.add_checkbutton(label="Enable Search Delay", variable=var_search_delay_enabled)
        options_menu.add_command(label="Set Search Delay", command=lambda: set_search_delay())
        options_menu.add_command(label="Change Background Color", command=lambda: change_background_color())
        options_menu.add_command(label="Change Theme", command=lambda: change_theme())
        options_menu.add_checkbutton(
            label="Auto-Paste from Clipboard on Focus",
            variable=root.auto_paste_enabled,
            command=save_settings
        )
        menu_bar.add_cascade(label="Options", menu=options_menu)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="Help", command=show_help)
        help_menu.add_command(label="About", command=show_about)
        help_menu.add_command(label="Clipboard History", command=show_clipboard_history)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        # --- Main UI ---
        town_label = ttk.Label(root, text="Select Town:")
        town_label.grid(row=0, column=0, padx=5, pady=5, sticky='e')
        town_var = tk.StringVar()
        town_dropdown = ttk.Combobox(root, textvariable=town_var, state='disabled', width=30)
        town_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky='we')
        town_dropdown['values'] = ['All Towns']
        town_dropdown.current(0)
        ttk.Label(root, text="Enter Address:").grid(row=1, column=0, padx=5, pady=5, sticky='e')
        entry_address = ttk.Entry(root, width=50)
        entry_address.grid(row=1, column=1, padx=5, pady=5, sticky='we')

        def clean_text(text):
            """Replace all tabs, newlines, and multiple spaces in text with a single space."""
            # Replace tabs/newlines with a space, then collapse ALL runs of whitespace to a single space
            return re.sub(r'\s+', ' ', text).strip()

        def clean_entry_after_paste(event=None):
            try:
                text = entry_address.get()
                cleaned = clean_text(text)
                if text != cleaned:
                    entry_address.delete(0, tk.END)
                    entry_address.insert(0, cleaned)
                    messagebox.showinfo("Clipboard Cleaned", cleaned)
                def delayed_trigger():
                    if getattr(root, 'file_loaded', False) and getattr(root, 'ready_for_search', False):
                        trigger_search()
                root.after(300, delayed_trigger)
            except Exception as e:
                logging.warning(f"clean_entry_after_paste error: {e}")

        # Bind all paste events to clean after paste
        entry_address.bind("<<Paste>>", lambda e: entry_address.after_idle(clean_entry_after_paste))
        entry_address.bind("<Command-v>", lambda e: entry_address.after_idle(clean_entry_after_paste))  # macOS
        entry_address.bind("<Control-v>", lambda e: entry_address.after_idle(clean_entry_after_paste))  # Windows/Linux

        def on_focus(event):
            try:
                if root.auto_paste_enabled.get():
                    text = root.clipboard_get()
                    if text and (not clipboard_history or text != clipboard_history[-1]):
                        clipboard_history.append(text)
                        if len(clipboard_history) > 10:
                            clipboard_history.pop(0)
                    entry_address.delete(0, tk.END)
                    entry_address.insert(0, clean_text(text))
                    def delayed_trigger():
                        if getattr(root, 'file_loaded', False) and getattr(root, 'ready_for_search', False):
                            trigger_search()
                    root.after(300, delayed_trigger)
            except Exception as e:
                logging.warning(f"on_focus error: {e}")
        root.bind("<FocusIn>", on_focus)

        def show_entry_context_menu(event):
            try:
                entry_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                entry_context_menu.grab_release()

        def paste_from_clipboard():
            try:
                entry_address.event_generate("<<Paste>>")
            except Exception as e:
                logging.error(f"Paste failed: {e}")

        entry_context_menu = tk.Menu(root, tearoff=0)
        entry_context_menu.add_command(label="Paste", command=paste_from_clipboard)
        entry_address.bind("<Button-3>", show_entry_context_menu)

        search_button = ttk.Button(root, text="Search", command=manual_search)
        if root.live_search_enabled:
            search_button.grid_remove()
        else:
            search_button.grid(row=1, column=2, padx=5, pady=5, sticky='w')

        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(2, weight=1)
        result_frame = ttk.Frame(root)
        result_frame.grid(row=2, column=0, columnspan=5, padx=5, pady=5, sticky='nsew')
        result_table = ttk.Treeview(result_frame, style='Treeview')
        result_table.pack(side='left', fill='both', expand=True)
        scrollbar_y = ttk.Scrollbar(result_frame, orient="vertical", command=result_table.yview)
        scrollbar_y.pack(side='right', fill='y')
        result_table.configure(yscrollcommand=scrollbar_y.set)
        scrollbar_x = ttk.Scrollbar(root, orient="horizontal", command=result_table.xview)
        scrollbar_x.grid(row=3, column=0, columnspan=5, sticky='we')
        result_table.configure(xscrollcommand=scrollbar_x.set)
        result_table['selectmode'] = 'extended'
        if root.live_search_enabled:
            entry_address.bind("<KeyRelease>", trigger_search)

        # --- Status bar and status lock ---
        status_label = ttk.Label(root, text="No file loaded.")
        status_label.grid(row=4, column=0, columnspan=5, padx=5, pady=5, sticky='we')

        status_lock = {"locked": False}

        def show_temp_status(msg, duration=1500):
            prev = status_label['text']
            status_lock["locked"] = True
            status_label.config(text=msg)
            def unlock():
                status_label.config(text=prev)
                status_lock["locked"] = False
            root.after(duration, unlock)

        def toggle_live_search():
            root.live_search_enabled = var_live_search.get()
            if root.live_search_enabled:
                search_button.grid_remove()
                entry_address.bind("<KeyRelease>", trigger_search)
                if getattr(root, 'col_indices', None) and root.col_indices.get('town') is not None:
                    town_dropdown.bind("<<ComboboxSelected>>", trigger_search)
                trigger_search()
                logging.info("Live search enabled.")
            else:
                search_button.grid(row=1, column=2, padx=5, pady=5, sticky='w')
                entry_address.unbind("<KeyRelease>")
                town_dropdown.unbind("<<ComboboxSelected>>")
                logging.info("Live search disabled.")

        def set_search_delay():
            def confirm_delay():
                try:
                    delay = int(delay_entry.get())
                    if delay < 0:
                        raise ValueError
                    root.search_delay = delay
                    logging.info(f"Search delay set to {delay} milliseconds.")
                    dialog.destroy()
                except ValueError:
                    messagebox.showerror("Invalid Input", "Please enter a non-negative integer for the delay.")
                    logging.error("Invalid search delay input.")
            dialog = tk.Toplevel(root)
            dialog.title("Set Search Delay")
            tk.Label(dialog, text="Enter search delay in milliseconds:").grid(row=0, column=0, padx=10, pady=10)
            delay_entry = tk.Entry(dialog)
            delay_entry.insert(0, str(root.search_delay))
            delay_entry.grid(row=0, column=1, padx=10, pady=10)
            tk.Button(dialog, text="OK", command=confirm_delay).grid(row=1, column=0, columnspan=2, pady=10)
            dialog.transient(root)
            dialog.grab_set()
            root.wait_window(dialog)

        def change_background_color():
            color_code = colorchooser.askcolor(title="Choose background color")[1]
            if color_code:
                root.configure(bg=color_code)
                logging.info(f"Background color changed to {color_code}.")

        def change_theme():
            available_themes = style.theme_names()
            current_theme = style.theme_use()
            def apply_theme():
                selected_theme = theme_var.get()
                style.theme_use(selected_theme)
                dialog.destroy()
                logging.info(f"Theme changed to {selected_theme}.")
            dialog = tk.Toplevel(root)
            dialog.title("Change Theme")
            tk.Label(dialog, text="Select a theme:").pack(padx=10, pady=10)
            theme_var = tk.StringVar(value=current_theme)
            for theme in available_themes:
                tk.Radiobutton(dialog, text=theme, variable=theme_var, value=theme).pack(anchor='w')
            tk.Button(dialog, text="Apply", command=apply_theme).pack(pady=10)
            dialog.transient(root)
            dialog.grab_set()
            root.wait_window(dialog)

        # Double-click on a result row to copy Location ID
        def on_double_click(event):
            try:
                item = result_table.selection()
                if item:
                    row_values = result_table.item(item)['values']
                    if 'Location ID' in result_table['columns']:
                        location_id_col = result_table['columns'].index('Location ID')
                        location_id = row_values[location_id_col]
                        root.clipboard_clear()
                        root.clipboard_append(str(location_id))
                        root.bell()
                        show_temp_status("Copied Location ID!", 1500)
            except Exception as e:
                logging.error(f"Double-click copy failed: {e}")
                messagebox.showerror("Error", f"Failed to copy Location ID:\n{e}")

        result_table.bind("<Double-1>", on_double_click)

        # Load settings and CSV if persistent
        load_settings()
        if root.persistent_file_enabled.get() and root.persistent_file_path:
            load_csv_file(root.persistent_file_path)

    # Splash screen loader in a thread
    def finish_loading():
        root.after(100, show_main_app)

    thread = threading.Thread(target=finish_loading)
    thread.start()
    splash.after(1200, finish_loading)  # Show splash for at least 1.2s
    root.mainloop()

if __name__ == "__main__":
    big_search_csv()
