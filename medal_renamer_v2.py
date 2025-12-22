import os
import sys
import json
import ctypes
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk
import subprocess
from datetime import datetime
import requests
import concurrent.futures
import hashlib
from collections import Counter, defaultdict

# --- Program beállítások és segédfüggvények ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

HISTORY_FILE = "restore_map.json"
CACHE_FILE = "local_hashes.json"
CONFIG_FILE = "config.json"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

try:
    myappid = 'umgkl.medal.uploader.v4.hash_sync'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except:
    pass


class DetectiveWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Nyomozó Mód")
        self.geometry("1100x700")
        self.parent = parent
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except:
            pass

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkLabel(self, text="Nyomozó Mód - hiányzó vagy feltöltetlen klipek diagnosztikája", font=ctk.CTkFont(size=18, weight="bold"))
        header.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="w")

        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.grid(row=1, column=0, sticky="ew", padx=20)
        progress_frame.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(progress_frame, text="Adatok összegyűjtése...", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w")
        self.progressbar = ctk.CTkProgressBar(progress_frame, progress_color="#27ae60")
        self.progressbar.grid(row=1, column=0, sticky="ew", pady=5)
        self.progressbar.set(0)

        table_frame = ctk.CTkFrame(self, fg_color="transparent")
        table_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(10, 20))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style(self)
        style.theme_use("default")
        style.configure(
            "Dark.Treeview",
            background="#2b2d31",
            fieldbackground="#2b2d31",
            foreground="white",
            bordercolor="#1e1f22",
            borderwidth=0,
            rowheight=26
        )
        style.configure("Dark.Treeview.Heading", background="#1e1f22", foreground="white", relief="flat")
        style.map("Dark.Treeview", background=[("selected", "#3a3f44")])

        columns = ("filename", "json_title", "filesystem", "hash", "server_status", "diagnosis")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            style="Dark.Treeview"
        )
        headings = {
            "filename": "Fájlnév",
            "json_title": "JSON Cím",
            "filesystem": "Fájlrendszer",
            "hash": "Hash",
            "server_status": "Szerver Státusz",
            "diagnosis": "Diagnózis"
        }
        for col, text in headings.items():
            self.tree.heading(col, text=text)
        self.tree.column("filename", width=220, anchor="w")
        self.tree.column("json_title", width=260, anchor="w")
        self.tree.column("filesystem", width=100, anchor="center")
        self.tree.column("hash", width=160, anchor="center")
        self.tree.column("server_status", width=120, anchor="center")
        self.tree.column("diagnosis", width=180, anchor="center")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.analysis_thread = threading.Thread(target=self.run_analysis, daemon=True)
        self.analysis_thread.start()

    def set_status(self, message):
        self.after(0, lambda: self.status_label.configure(text=message))

    def set_progress(self, value):
        self.after(0, lambda: self.progressbar.set(value))

    def populate_table(self, rows):
        for row in rows:
            self.tree.insert("", "end", values=row)
        if not rows:
            self.tree.insert("", "end", values=("-", "-", "-", "-", "-", "Nincs adat"))

    def run_analysis(self):
        try:
            json_path = self.parent.entry_json.get().strip()
            video_path = self.parent.entry_video.get().strip()
            server_url = self.parent.entry_server.get().strip()

            if not all([json_path, video_path, server_url]):
                self.set_status("Hiányzó beállítások. Töltsd ki a főablak mezőit.")
                return

            if not os.path.exists(json_path):
                self.set_status("A megadott clips.json nem található.")
                return

            self.set_status("JSON beolvasása...")
            with open(json_path, 'r', encoding='utf-8') as f:
                raw_clips = {}
                self.parent.extract_mapping_recursive(json.load(f), raw_clips)

            self.set_status("Helyi fájlok feltérképezése...")
            file_map = {}
            for root, _, files in os.walk(video_path):
                for file in files:
                    if file.lower().endswith('.mp4'):
                        file_map[file.lower()] = os.path.join(root, file)

            cache = {}
            if os.path.exists(CACHE_FILE):
                try:
                    with open(CACHE_FILE, 'r') as f:
                        cache = json.load(f)
                except Exception:
                    cache = {}

            needs_update = False
            entries = {}
            for name, title in raw_clips.items():
                key = name.lower()
                entries.setdefault(key, {"filename": name, "json_title": title, "in_json": True, "in_fs": False})
                entries[key]["json_title"] = title
                entries[key]["in_json"] = True

            for lower_name, path in file_map.items():
                display_name = os.path.basename(path)
                entry = entries.setdefault(lower_name, {"filename": display_name, "json_title": "", "in_json": False, "in_fs": False})
                entry["filename"] = entry.get("filename") or display_name
                entry["filepath"] = path
                entry["in_fs"] = True

            all_items = list(entries.values())
            total_items = len(all_items) if all_items else 1
            hash_to_entries = defaultdict(list)

            for idx, entry in enumerate(all_items):
                if entry.get("in_fs"):
                    path = entry.get("filepath")
                    if path and os.path.exists(path):
                        mtime = os.path.getmtime(path)
                        cache_key = entry.get("filename")
                        cached = cache.get(cache_key)
                        if cached and cached.get('mtime') == mtime:
                            file_hash = cached.get('hash')
                        else:
                            file_hash = self.parent.calculate_file_hash(path)
                            if file_hash:
                                cache[cache_key] = {'hash': file_hash, 'mtime': mtime}
                                needs_update = True
                        entry["hash"] = file_hash
                        if file_hash:
                            hash_to_entries[file_hash].append(entry)
                self.set_progress((idx + 1) / total_items)

            if needs_update:
                try:
                    with open(CACHE_FILE, 'w') as f:
                        json.dump(cache, f, indent=2)
                except Exception:
                    pass

            self.set_status("Szerver státusz lekérdezése...")
            server_hashes = None
            try:
                api_endpoint = f"{server_url.rstrip('/')}/api/videos/get-uploaded-hashes"
                response = requests.get(api_endpoint, timeout=10)
                response.raise_for_status()
                server_hashes = set(response.json())
            except Exception as e:
                self.set_status(f"Nem sikerült a szerver lekérdezése: {e}")

            rows = []
            for entry in all_items:
                filename = entry.get("filename", "-")
                title = entry.get("json_title", "") or "-"
                in_fs = entry.get("in_fs", False)
                file_hash = entry.get("hash")
                hash_short = file_hash[:12] + "..." if file_hash else "-"

                if server_hashes is None:
                    server_status = "Ismeretlen"
                else:
                    server_status = "FENT VAN" if file_hash and file_hash in server_hashes else "NINCS FENT"

                if entry.get("in_json") and not in_fs:
                    diagnosis = "Hiányzó fájl"
                elif in_fs and not entry.get("in_json"):
                    diagnosis = "Nincs a JSON-ban"
                elif file_hash and len(hash_to_entries[file_hash]) > 1:
                    diagnosis = "Hash ütközés"
                elif in_fs and file_hash and server_status == "FENT VAN":
                    diagnosis = "Rendben"
                elif in_fs and not file_hash:
                    diagnosis = "Hash hiba"
                else:
                    diagnosis = "Nincs feltöltve"

                rows.append((
                    filename,
                    title,
                    "IGEN" if in_fs else "NEM",
                    hash_short,
                    server_status,
                    diagnosis
                ))

            self.set_status("Kész")
            self.set_progress(1)
            self.after(0, lambda: self.populate_table(rows))
        except Exception as e:
            self.set_status(f"Hiba történt: {e}")


class ConflictDialog(ctk.CTkToplevel):
    # Ez a class változatlan, a régi átnevezéshez kell
    def __init__(self, parent, original_file, target_name, path):
        super().__init__(parent)
        self.title("Névütközés Megoldása")
        self.geometry("600x380")
        self.result = None
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except: pass
        self.attributes("-topmost", True)
        self.transient(parent)
        self.grab_set() 
        ctk.CTkLabel(self, text="⚠️ Már létezik ilyen nevű fájl!", font=ctk.CTkFont(size=18, weight="bold"), text_color="#e74c3c").pack(pady=(20, 10))
        info_frame = ctk.CTkFrame(self, fg_color="#2b2d31")
        info_frame.pack(fill="x", padx=20, pady=10)
        self.create_info_row(info_frame, "Eredeti fájl:", original_file)
        self.create_info_row(info_frame, "Mappa:", path)
        self.create_info_row(info_frame, "Erre akartuk nevezni:", target_name, text_color="#f1c40f")
        ctk.CTkLabel(self, text="Adj meg egy új nevet (kiterjesztés nélkül):").pack(pady=(10, 5))
        self.name_entry = ctk.CTkEntry(self, width=400)
        self.name_entry.insert(0, os.path.splitext(target_name)[0] + "_alt")
        self.name_entry.pack(pady=5); self.name_entry.focus_set()
        btn_frame = ctk.CTkFrame(self, fg_color="transparent"); btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Kihagyás", fg_color="#7f8c8d", hover_color="#95a5a6", command=self.on_skip).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Mentés az új névvel", fg_color="#7289da", hover_color="#5b6eae", command=self.on_save).pack(side="left", padx=10)
        self.protocol("WM_DELETE_WINDOW", self.on_skip)
    def create_info_row(self, parent, label, value, text_color="silver"):
        row = ctk.CTkFrame(parent, fg_color="transparent"); row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(weight="bold", size=12), width=100, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=value, text_color=text_color, anchor="w").pack(side="left", fill="x", expand=True)
    def on_save(self):
        new_name = self.name_entry.get().strip()
        if not new_name: messagebox.showwarning("Hiba", "A név nem lehet üres!", parent=self); return
        self.result = new_name if new_name.endswith(".mp4") else new_name + ".mp4"; self.destroy()
    def on_skip(self): self.result = None; self.destroy()

class MedalUploaderTool(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("UMKGL - Medal Klip Előkészítő v4 (Hash alapú szinkronizálás)")
        self.geometry("800x800")

        try:
            self.iconbitmap(resource_path("icon.ico"))
        except: pass

        self.label_title = ctk.CTkLabel(self, text="Medal Klip Előkészítő", font=ctk.CTkFont(size=24, weight="bold"))
        self.label_title.pack(pady=15)

        self.config_data = self.load_config()

        self.stop_event = threading.Event()
        self.processing_thread = None

        # GUI elemek
        self.create_path_entry("1. Medal Adatbázis (clips.json):", "entry_json", self.browse_json, self.config_data.get("json_path", ""))
        self.create_path_entry("2. Medal Klipek Mappája:", "entry_video", self.browse_video, self.config_data.get("video_path", ""))
        self.create_path_entry("3. Weboldal Címe (URL):", "entry_server", None, self.config_data.get("server_url", ""))
        self.create_path_entry("4. Célmappa (ide kerülnek a feltöltendők):", "entry_output", self.browse_output, self.config_data.get("output_path", ""))

        encoder_frame = ctk.CTkFrame(self)
        encoder_frame.pack(fill="x", padx=20, pady=(5, 10))
        ctk.CTkLabel(encoder_frame, text="Kódolás típusa:", width=250, anchor="w").pack(side="left", padx=10)
        self.encoder_menu = ctk.CTkOptionMenu(
            encoder_frame,
            values=["CPU (Lassú, Stabil)", "NVIDIA (NVENC)", "AMD (AMF)"],
            width=220
        )
        self.encoder_menu.pack(side="left", padx=10)
        self.encoder_menu.set(self.config_data.get("encoder", "CPU (Lassú, Stabil)"))

        self.btn_detective = ctk.CTkButton(
            self,
            text="NYOMOZÓ MÓD 🔍",
            height=40,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#8e44ad",
            hover_color="#9b59b6",
            command=self.open_detective_mode
        )
        self.btn_detective.pack(fill="x", padx=20, pady=(10, 5))

        self.btn_preview = ctk.CTkButton(self, text="ELŐNÉZET / TESZT", height=50,
                                       font=ctk.CTkFont(size=16, weight="bold"),
                                       fg_color="#5b6eae", hover_color="#7289da",
                                       command=lambda: self.start_processing_thread(dry_run=True))
        self.btn_preview.pack(fill="x", padx=20, pady=(20, 10))

        self.btn_prepare = ctk.CTkButton(self, text="ÚJ KLIPPEK EXPORTÁLÁSA", height=50,
                                       font=ctk.CTkFont(size=16, weight="bold"),
                                       fg_color="#27ae60", hover_color="#2ecc71",
                                       command=lambda: self.start_processing_thread(dry_run=False))
        self.btn_prepare.pack(fill="x", padx=20, pady=(0, 10))

        self.textbox_label = ctk.CTkLabel(self, text="Folyamatnapló (Konzol)", font=ctk.CTkFont(size=14))
        self.textbox_label.pack(pady=(10, 2))
        self.textbox = ctk.CTkTextbox(self, height=200, font=("Consolas", 12))
        self.textbox.pack(fill="both", padx=20, pady=5)

        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.progressbar = ctk.CTkProgressBar(progress_frame, progress_color="#27ae60")
        self.progressbar.pack(side="left", fill="x", expand=True, pady=(0, 5))
        self.btn_stop = ctk.CTkButton(
            progress_frame,
            text="LEÁLLÍTÁS",
            fg_color="#e74c3c",
            hover_color="#c0392b",
            state="disabled",
            command=self.request_stop
        )
        self.btn_stop.pack(side="left", padx=(10, 0), pady=(0, 5))
        self.progressbar.set(0)

        self.filename_to_title = {}
        self.log_counter = 0
        self.path_lock = threading.Lock()
        self.log("Program indítva. Add meg az elérési utakat, majd kattints a zöld gombra.")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_path_entry(self, label_text, entry_attr, browse_cmd, default_text=""):
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame, text=label_text, width=250, anchor="w").pack(side="left", padx=10)
        entry = ctk.CTkEntry(frame, placeholder_text="...")
        entry.pack(side="left", fill="x", expand=True)
        if default_text is not None:
            entry.insert(0, default_text)
        setattr(self, entry_attr, entry)
        if browse_cmd:
            ctk.CTkButton(frame, text="Tallózás", width=80, command=browse_cmd).pack(side="right", padx=10)

    def get_default_config(self):
        appdata = os.getenv('APPDATA') or ""
        default_json = ""
        if appdata:
            candidate = os.path.join(appdata, 'Medal', 'store', 'clips.json')
            if os.path.exists(candidate):
                default_json = candidate

        desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
        default_output = os.path.join(desktop_path, 'Export_Klippek')

        return {
            "json_path": default_json,
            "video_path": "",
            "server_url": "http://api.umkgl.online:3000",
            "output_path": default_output,
            "encoder": "CPU (Lassú, Stabil)",
        }

    def load_config(self):
        defaults = self.get_default_config()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                defaults.update({
                    "json_path": data.get("json_path", defaults["json_path"]),
                    "video_path": data.get("video_path", defaults["video_path"]),
                    "server_url": data.get("server_url", defaults["server_url"]),
                    "output_path": data.get("output_path", defaults["output_path"]),
                    "encoder": data.get("encoder", defaults["encoder"]),
                })
            except Exception:
                pass
        return defaults

    def save_config(self):
        data = {
            "json_path": self.entry_json.get().strip(),
            "video_path": self.entry_video.get().strip(),
            "server_url": self.entry_server.get().strip(),
            "output_path": self.entry_output.get().strip(),
            "encoder": self.encoder_menu.get(),
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"Nem sikerült menteni a beállításokat: {e}")

    def format_size(self, size_bytes):
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(size_bytes)
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.2f} {unit}"
            size /= 1024

    def sanitize_title(self, title, fallback_name):
        clean_title = "".join([c for c in title if c not in '<>:"/\\|?*']).strip()
        if not clean_title:
            clean_title = os.path.splitext(fallback_name)[0]
        return f"{clean_title}.mp4"

    def set_buttons_state(self, state):
        self.after(0, lambda: (self.btn_preview.configure(state=state), self.btn_prepare.configure(state=state)))

    def set_stop_button_state(self, state):
        self.after(0, lambda: self.btn_stop.configure(state=state))

    def open_detective_mode(self):
        DetectiveWindow(self)

    def start_processing_thread(self, dry_run=False):
        self.set_buttons_state("disabled")
        self.set_stop_button_state("normal")
        self.stop_event.clear()
        self.processing_thread = threading.Thread(target=self.run_sync, args=(dry_run,), daemon=True)
        self.processing_thread.start()

    def log(self, msg, force_update=False):
        def append_message():
            self.log_counter += 1
            self.textbox.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            if force_update or self.log_counter % 10 == 0:
                self.textbox.see("end")
        self.after(0, append_message)

    def request_stop(self):
        if not self.stop_event.is_set():
            self.log("Leállítás kérése folyamatban...")
            self.stop_event.set()
        self.set_stop_button_state("disabled")

    def browse_json(self): self.browse_file(self.entry_json, [("JSON files", "*.json")])
    def browse_video(self): self.browse_dir(self.entry_video)
    def browse_output(self): self.browse_dir(self.entry_output)
    def browse_file(self, entry, filetypes): f = filedialog.askopenfilename(filetypes=filetypes); entry.delete(0, "end"); entry.insert(0, f)
    def browse_dir(self, entry): d = filedialog.askdirectory(); entry.delete(0, "end"); entry.insert(0, d)
    
    def calculate_file_hash(self, filepath):
        sha1 = hashlib.sha1()
        try:
            with open(filepath, 'rb') as f:
                # Csak az első 5 MB-ot olvassuk be a sebesség miatt
                buffer = f.read(5 * 1024 * 1024) 
                sha1.update(buffer)
            return sha1.hexdigest()
        except Exception as e:
            self.log(f"HIBA: Nem sikerült olvasni a fájlt a hash-eléshez: {filepath} ({e})")
            return None

    def get_video_codec(self, source_path):
        try:
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=codec_name',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    source_path
                ],
                capture_output=True,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if result.returncode == 0:
                return result.stdout.strip().lower()
            else:
                self.log(f"  -> FIGYELEM: ffprobe hiba ({source_path}): {result.stderr.strip()}")
        except FileNotFoundError:
            self.log("[HIBA] Az 'ffprobe' nem található! A kodek ellenőrzés kihagyva.")
        except Exception as e:
            self.log(f"  -> HIBA a kodek ellenőrzésekor ({source_path}): {e}")
        return None

    def get_video_height(self, source_path):
        try:
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=height',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    source_path
                ],
                capture_output=True,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if result.returncode == 0:
                height_str = result.stdout.strip()
                return int(height_str) if height_str.isdigit() else None
            else:
                self.log(f"  -> FIGYELEM: ffprobe hiba (magasság) ({source_path}): {result.stderr.strip()}")
        except FileNotFoundError:
            self.log("[HIBA] Az 'ffprobe' nem található! A magasság ellenőrzés kihagyva.")
        except Exception as e:
            self.log(f"  -> HIBA a magasság ellenőrzésekor ({source_path}): {e}")
        return None

    def process_single_clip(self, clip_info, video_path, output_path, original_hash, encoder_type):
        if self.stop_event.is_set():
            return False, "  -> Megszakítva a felhasználó által."
        original_name, title = clip_info['original_name'], clip_info['title']
        source_path = clip_info['source_path']
        target_name = self.sanitize_title(title, original_name)

        # Az eredeti videófolyam változtatás nélküli átmásolása (nincs tömörítés vagy átméretezés)
        video_encoder_params = ['-c', 'copy']
        allow_fallback = False

        relative_folder = os.path.relpath(os.path.dirname(source_path), video_path)
        target_dir = os.path.join(output_path, relative_folder)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, target_name)

        with self.path_lock:
            counter = 1
            while os.path.exists(target_path):
                name, ext = os.path.splitext(target_name)
                target_path = os.path.join(target_dir, f"{name}_{counter}{ext}")
                counter += 1

        try:
            creation_timestamp = os.path.getmtime(source_path)
            creation_datetime = datetime.fromtimestamp(creation_timestamp)
            formatted_date = creation_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')

            self.log(f"  -> Export: {original_name} -> {os.path.basename(target_path)}")
            # Az eredeti felbontás megtartása, nincs skálázás
            self.log("     Átméretezés: Nem történik, eredeti felbontás megtartva.")

            def build_command(video_params):
                cmd = ['ffmpeg', '-i', source_path]
                cmd.extend(video_params)
                cmd.extend([
                    '-metadata', f'creation_time={formatted_date}',
                    '-metadata', f'comment=UMKGL_HASH:{original_hash}',
                    '-movflags', '+faststart',
                    '-y', target_path
                ])
                return cmd

            command = build_command(video_encoder_params)

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            if result.returncode != 0 and allow_fallback:
                self.log("GPU kódolás sikertelen, váltás a megbízható CPU módra...")
                command = build_command(cpu_encoder)
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )

            if result.returncode == 0:
                return True, f"  -> KÉSZ: {os.path.basename(target_path)} (dátum: {creation_datetime.strftime('%Y.%m.%d %H:%M')})"
            else:
                return False, f"  -> META HIBA: ffmpeg hiba ({original_name}):\n{result.stderr.strip()}"
        except FileNotFoundError:
            return False, "[HIBA] Az 'ffmpeg.exe' nem található! A metaadatok javítása kihagyva."
        except Exception as e:
            return False, f"  -> HIBA a feldolgozás során ({original_name}): {e}"

    def run_sync(self, dry_run=False):
        try:
            json_path = self.entry_json.get().strip()
            video_path = self.entry_video.get().strip()
            server_url = self.entry_server.get().strip()
            output_path = self.entry_output.get().strip()
            encoder_type = self.encoder_menu.get()

            self.progressbar.set(0)

            if not all([json_path, video_path, server_url, output_path]):
                messagebox.showerror("Hiba", "Minden mezőt ki kell tölteni!")
                return

            header = "ELŐNÉZET / TESZT" if dry_run else "ÚJ KLIPPEK EXPORTÁLÁSA"
            self.log(f"\n--- {header} (HASH ALAPÚ SZINKRONIZÁLÁS) ---", force_update=True)

            cache = {}
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r') as f:
                    cache = json.load(f)

            # Fájlok rekurzív feltérképezése az almappákkal együtt
            file_map = {}
            mp4_count = 0
            for root, _, files in os.walk(video_path):
                for file in files:
                    if file.lower().endswith('.mp4'):
                        mp4_count += 1
                        abs_path = os.path.abspath(os.path.join(root, file))
                        file_map.setdefault(file.lower(), abs_path)

            self.log(f"Találtam {mp4_count} fájlt a mapparendszerben.")

            with open(json_path, 'r', encoding='utf-8') as f:
                raw_clips = {}
                self.extract_mapping_recursive(json.load(f), raw_clips)

            local_hashes = {}
            needs_update = False
            missing_files = []

            missing_debug_logged = 0

            total_items = len(raw_clips)

            for i, (original_name, title) in enumerate(raw_clips.items()):
                if self.stop_event.is_set():
                    self.log("Folyamat megszakítva elemzés közben.")
                    break
                self.log(f"  Elemzés: {i + 1}/{len(raw_clips)} - {original_name}")
                file_path = file_map.get(original_name.lower())

                if (not file_path) or (not os.path.exists(file_path)):
                    clean_filename = self.sanitize_title(title, original_name).lower()
                    file_path = file_map.get(clean_filename)

                if not file_path or not os.path.exists(file_path):
                    missing_files.append(original_name)
                    if missing_debug_logged < 3:
                        self.log(f"[DEBUG] Nem található a térképben: '{original_name}'")
                        missing_debug_logged += 1
                    continue

                mtime = os.path.getmtime(file_path)

                if original_name in cache and cache[original_name].get('mtime') == mtime:
                    file_hash = cache[original_name]['hash']
                else:
                    file_hash = self.calculate_file_hash(file_path)
                    if file_hash:
                        cache[original_name] = {'hash': file_hash, 'mtime': mtime}
                        needs_update = True

                if file_hash:
                    local_hashes[file_hash] = {
                        'original_name': original_name,
                        'title': title,
                        'size': os.path.getsize(file_path),
                        'source_path': file_path,
                        'hash': file_hash
                    }

                if total_items:
                    self.progressbar.set((i + 1) / total_items)

            if needs_update and not dry_run:
                with open(CACHE_FILE, 'w') as f:
                    json.dump(cache, f, indent=2)

            self.log(f"Helyi klipek elemzése kész. {len(local_hashes)} érvényes klip azonosítva.")
            self.progressbar.set(0)
            if missing_files:
                self.log(f"Figyelem: {len(missing_files)} fájl nem található a klipek mappájában.")

            if self.stop_event.is_set():
                self.log("Megszakítva a felhasználó által az elemzés után.")
                self.save_config()
                return

            self.log("Kapcsolódás a szerverhez...")
            api_endpoint = f"{server_url.rstrip('/')}/api/videos/get-uploaded-hashes"
            response = requests.get(api_endpoint, timeout=10)
            response.raise_for_status()
            server_hashes = set(response.json())
            self.log(f"Szerveren lévő klipek (hash) száma: {len(server_hashes)}.")

            files_to_process = []
            total_missing_size = 0
            for file_hash, clip_info in local_hashes.items():
                if file_hash not in server_hashes:
                    files_to_process.append(clip_info)
                    total_missing_size += clip_info['size']

            self.log(f"Helyi klipek száma: {len(local_hashes)} db")
            self.log(f"Ebből új, feltöltendő: {len(files_to_process)} db")
            self.log(f"A várható export mérete: {self.format_size(total_missing_size)}")

            if dry_run:
                if not files_to_process:
                    messagebox.showinfo("Naprakész", "Minden helyi kliped már fent van a weboldalon!")
                else:
                    messagebox.showinfo("Előnézet kész", "A naplóban láthatod a várható export részleteit.")
                self.save_config()
                return

            if not files_to_process:
                self.log("\nNem található új, feltöltésre váró klip.")
                messagebox.showinfo("Naprakész", "Minden helyi kliped már fent van a weboldalon!")
                self.save_config()
                return

            os.makedirs(output_path, exist_ok=True)
            self.log(f"\nExportálás: {len(files_to_process)} új klip másolása és javítása...")
            copied_count = 0
            processed_exports = 0
            total_exports = len(files_to_process)

            executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
            try:
                future_to_clip = {}
                for clip_info in files_to_process:
                    if self.stop_event.is_set():
                        self.log("Exportálás megszakítva a felhasználó által (indítás előtt).")
                        break
                    future = executor.submit(self.process_single_clip, clip_info, video_path, output_path, clip_info['hash'], encoder_type)
                    future_to_clip[future] = clip_info

                if future_to_clip:
                    for future in concurrent.futures.as_completed(future_to_clip):
                        if self.stop_event.is_set():
                            self.log("Exportálás megszakítva, várakozó feladatok leállítása...")
                            break
                        success, message = future.result()
                        if message:
                            self.log(message)
                        if success:
                            copied_count += 1

                        processed_exports += 1
                        if total_exports:
                            self.progressbar.set(processed_exports / total_exports)
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

            if self.stop_event.is_set():
                self.log("Folyamat leállítva a felhasználó kérésére.")
                self.save_config()
                return

            self.log("-" * 30)
            self.log(f"KÉSZ! {copied_count} új klip előkészítve a '{output_path}' mappába.")
            messagebox.showinfo("Siker", f"{copied_count} új klip átmásolva és előkészítve a feltöltéshez!")
            self.save_config()

        except requests.exceptions.RequestException as e:
            self.log("SZERVER HIBA: Nem sikerült elérni a weboldalt. Ellenőrizd az URL-t és a szerver állapotát.")
            messagebox.showerror("Szerver Hiba", f"Nem sikerült kapcsolódni a szerverhez:\n{e}")
        except Exception as e:
            self.log(f"Kritikus hiba: {e}")
            messagebox.showerror("Hiba", f"Váratlan hiba történt:\n{e}")
        finally:
            self.set_buttons_state("normal")
            self.set_stop_button_state("disabled")
            self.processing_thread = None

    # A régi függvények itt kezdődnek (változatlanul)
    def extract_mapping_recursive(self, data, result_dict):
        if isinstance(data, dict):
            path_val = data.get('localContentUrl') or data.get('FilePath') or data.get('videoFile')
            title = data.get('contentTitle')
            if title and path_val and isinstance(path_val, str):
                filename = os.path.basename(path_val.replace("\\", "/")); result_dict[filename] = title
            for v in data.values(): self.extract_mapping_recursive(v, result_dict)
        elif isinstance(data, list):
            for item in data: self.extract_mapping_recursive(item, result_dict)

    def on_close(self):
        self.stop_event.set()
        self.after(100, self.check_threads_and_destroy)

    def check_threads_and_destroy(self):
        if not self.processing_thread or not self.processing_thread.is_alive():
            self.save_config()
            self.destroy()
        else:
            self.after(100, self.check_threads_and_destroy)

if __name__ == "__main__":
    app = MedalUploaderTool()
    app.mainloop()
