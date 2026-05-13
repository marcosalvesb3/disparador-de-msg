import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from dotenv import load_dotenv, set_key

from whatsapp_sender import (
    build_template_payload,
    build_text_payload,
    read_contacts,
    send_payload,
)


APP_TITLE = "Disparador de MSG"
ENV_PATH = ".env"


class WhatsAppSenderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        load_dotenv()

        self.title(APP_TITLE)
        self.geometry("920x680")
        self.minsize(820, 600)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.stop_requested = False

        self.contacts_path = tk.StringVar(value="contacts.example.csv")
        self.access_token = tk.StringVar(value=os.getenv("WHATSAPP_ACCESS_TOKEN", ""))
        self.phone_number_id = tk.StringVar(value=os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""))
        self.api_version = tk.StringVar(value=os.getenv("WHATSAPP_API_VERSION", "v23.0"))
        self.delay = tk.DoubleVar(value=2.0)
        self.timeout = tk.IntVar(value=30)
        self.use_template = tk.BooleanVar(value=False)
        self.template_name = tk.StringVar()
        self.template_language = tk.StringVar(value="pt_BR")
        self.template_vars = tk.StringVar()

        self._build_style()
        self._build_ui()
        self.after(120, self._drain_log_queue)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f6f7f9")
        style.configure("Panel.TFrame", background="#ffffff", relief="flat")
        style.configure("TLabel", background="#f6f7f9", foreground="#1f2937", font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background="#ffffff")
        style.configure("Title.TLabel", background="#f6f7f9", foreground="#111827", font=("Segoe UI Semibold", 18))
        style.configure("Hint.TLabel", background="#ffffff", foreground="#6b7280", font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        style.configure("Primary.TButton", font=("Segoe UI Semibold", 10), padding=(14, 8))
        style.configure("Danger.TButton", font=("Segoe UI Semibold", 10), padding=(14, 8))
        style.configure("TCheckbutton", background="#ffffff", foreground="#1f2937", font=("Segoe UI", 10))

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X, pady=(0, 14))
        ttk.Label(header, text="Disparador de MSG", style="Title.TLabel").pack(side=tk.LEFT)

        actions = ttk.Frame(header)
        actions.pack(side=tk.RIGHT)
        self.simulate_button = ttk.Button(actions, text="Simular", command=lambda: self._start(send=False))
        self.simulate_button.pack(side=tk.LEFT, padx=(0, 8))
        self.send_button = ttk.Button(actions, text="Enviar", style="Primary.TButton", command=lambda: self._start(send=True))
        self.send_button.pack(side=tk.LEFT, padx=(0, 8))
        self.stop_button = ttk.Button(actions, text="Parar", style="Danger.TButton", command=self._stop, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)

        body = ttk.Frame(root)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="Panel.TFrame", padding=16)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 14))

        right = ttk.Frame(body, style="Panel.TFrame", padding=16)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self._build_settings(left)
        self._build_log(right)

    def _build_settings(self, parent: ttk.Frame) -> None:
        self._field(parent, "CSV de contatos", self.contacts_path, browse=True)
        self._field(parent, "Access Token", self.access_token, secret=True)
        self._field(parent, "Phone Number ID", self.phone_number_id)
        self._field(parent, "API Version", self.api_version)

        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill=tk.X, pady=(10, 0))
        self._number_field(row, "Pausa", self.delay, 0, 999, 0.5, "segundos")
        self._number_field(row, "Timeout", self.timeout, 5, 300, 5, "segundos")

        template_box = ttk.LabelFrame(parent, text="Template aprovado", padding=12)
        template_box.pack(fill=tk.X, pady=(16, 0))
        template_box.configure(style="Panel.TFrame")
        ttk.Checkbutton(template_box, text="Usar template", variable=self.use_template, command=self._toggle_template).pack(anchor=tk.W)
        self.template_name_entry = self._field(template_box, "Nome do template", self.template_name, disabled=True)
        self.template_language_entry = self._field(template_box, "Idioma", self.template_language, disabled=True)
        self.template_vars_entry = self._field(template_box, "Variaveis do CSV", self.template_vars, disabled=True)
        ttk.Label(template_box, text="Exemplo: name message", style="Hint.TLabel").pack(anchor=tk.W, pady=(0, 4))

        ttk.Button(parent, text="Salvar credenciais", command=self._save_env).pack(fill=tk.X, pady=(18, 0))
        ttk.Button(parent, text="Carregar contatos", command=self._preview_contacts).pack(fill=tk.X, pady=(8, 0))

    def _build_log(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent, style="Panel.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Log", style="Panel.TLabel", font=("Segoe UI Semibold", 12)).pack(side=tk.LEFT)
        ttk.Button(top, text="Limpar", command=self._clear_log).pack(side=tk.RIGHT)

        self.log = tk.Text(parent, wrap=tk.WORD, height=20, bg="#0f172a", fg="#e5e7eb", insertbackground="#e5e7eb", relief=tk.FLAT, padx=12, pady=12)
        self.log.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.log.configure(state=tk.DISABLED)

    def _field(self, parent: ttk.Frame, label: str, variable: tk.StringVar, browse: bool = False, secret: bool = False, disabled: bool = False) -> ttk.Entry:
        ttk.Label(parent, text=label, style="Panel.TLabel").pack(anchor=tk.W, pady=(10, 3))
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill=tk.X)
        entry = ttk.Entry(row, textvariable=variable, width=42, show="*" if secret else "")
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if disabled:
            entry.configure(state=tk.DISABLED)
        if browse:
            ttk.Button(row, text="Escolher", command=self._choose_csv).pack(side=tk.LEFT, padx=(8, 0))
        return entry

    def _number_field(self, parent: ttk.Frame, label: str, variable: tk.Variable, start: float, end: float, step: float, suffix: str) -> None:
        box = ttk.Frame(parent, style="Panel.TFrame")
        box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Label(box, text=label, style="Panel.TLabel").pack(anchor=tk.W, pady=(0, 3))
        spin = ttk.Spinbox(box, textvariable=variable, from_=start, to=end, increment=step, width=8)
        spin.pack(side=tk.LEFT)
        ttk.Label(box, text=suffix, style="Panel.TLabel").pack(side=tk.LEFT, padx=(6, 0))

    def _choose_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="Escolher CSV de contatos",
            filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*.*")],
        )
        if path:
            self.contacts_path.set(path)

    def _toggle_template(self) -> None:
        state = tk.NORMAL if self.use_template.get() else tk.DISABLED
        for entry in (self.template_name_entry, self.template_language_entry, self.template_vars_entry):
            entry.configure(state=state)

    def _save_env(self) -> None:
        if not os.path.exists(ENV_PATH):
            open(ENV_PATH, "a", encoding="utf-8").close()
        set_key(ENV_PATH, "WHATSAPP_ACCESS_TOKEN", self.access_token.get().strip())
        set_key(ENV_PATH, "WHATSAPP_PHONE_NUMBER_ID", self.phone_number_id.get().strip())
        set_key(ENV_PATH, "WHATSAPP_API_VERSION", self.api_version.get().strip() or "v23.0")
        messagebox.showinfo(APP_TITLE, "Credenciais salvas no arquivo .env.")

    def _preview_contacts(self) -> None:
        try:
            contacts = read_contacts(self.contacts_path.get())
        except Exception as error:
            messagebox.showerror(APP_TITLE, str(error))
            return

        self._log(f"Contatos carregados: {len(contacts)}")
        for contact in contacts[:8]:
            label = contact.name or "(sem nome)"
            self._log(f"- {label} | {contact.phone}")
        if len(contacts) > 8:
            self._log(f"... e mais {len(contacts) - 8} contatos")

    def _start(self, send: bool) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(APP_TITLE, "Ja existe um envio em andamento.")
            return

        if send:
            confirmed = messagebox.askyesno(
                APP_TITLE,
                "Enviar mensagens reais agora?\n\nConfirme apenas se estes contatos autorizaram o recebimento.",
            )
            if not confirmed:
                return

        self.stop_requested = False
        self._set_running(True)
        self.worker = threading.Thread(target=self._run_sender, args=(send,), daemon=True)
        self.worker.start()

    def _stop(self) -> None:
        self.stop_requested = True
        self._log("Parada solicitada. O envio vai encerrar apos o contato atual.")

    def _run_sender(self, send: bool) -> None:
        successes = 0
        failures = 0

        try:
            contacts = read_contacts(self.contacts_path.get())
            self.log_queue.put(f"Contatos carregados: {len(contacts)}")
            self.log_queue.put("Modo: ENVIO REAL" if send else "Modo: SIMULACAO")

            access_token = self.access_token.get().strip()
            phone_number_id = self.phone_number_id.get().strip()
            api_version = self.api_version.get().strip() or "v23.0"
            template_vars = [item.strip() for item in self.template_vars.get().split() if item.strip()]

            if send and (not access_token or not phone_number_id):
                raise ValueError("Preencha Access Token e Phone Number ID para enviar de verdade.")
            if self.use_template.get() and not self.template_name.get().strip():
                raise ValueError("Informe o nome do template aprovado.")

            for position, contact in enumerate(contacts, start=1):
                if self.stop_requested:
                    self.log_queue.put("Envio interrompido pelo usuario.")
                    break

                label = contact.name or contact.phone
                try:
                    if self.use_template.get():
                        payload = build_template_payload(
                            contact,
                            self.template_name.get().strip(),
                            self.template_language.get().strip() or "pt_BR",
                            template_vars,
                        )
                    else:
                        payload = build_text_payload(contact)

                    if send:
                        result = send_payload(payload, access_token, phone_number_id, api_version, int(self.timeout.get()))
                        message_id = result.get("messages", [{}])[0].get("id", "sem-id")
                        self.log_queue.put(f"[{position}/{len(contacts)}] Enviado para {label}: {message_id}")
                    else:
                        self.log_queue.put(f"[{position}/{len(contacts)}] Simulado para {label}")
                    successes += 1

                    if send and position < len(contacts) and not self.stop_requested:
                        time.sleep(max(float(self.delay.get()), 0))
                except Exception as error:
                    failures += 1
                    self.log_queue.put(f"[{position}/{len(contacts)}] Falha para {label}: {error}")

            self.log_queue.put(f"Finalizado. Sucessos: {successes}. Falhas: {failures}.")
        except Exception as error:
            self.log_queue.put(f"Erro: {error}")
        finally:
            self.log_queue.put("__DONE__")

    def _set_running(self, running: bool) -> None:
        state = tk.DISABLED if running else tk.NORMAL
        self.simulate_button.configure(state=state)
        self.send_button.configure(state=state)
        self.stop_button.configure(state=tk.NORMAL if running else tk.DISABLED)

    def _drain_log_queue(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item == "__DONE__":
                    self._set_running(False)
                else:
                    self._log(item)
        except queue.Empty:
            pass
        self.after(120, self._drain_log_queue)

    def _log(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, f"{text}\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _clear_log(self) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)


if __name__ == "__main__":
    app = WhatsAppSenderApp()
    app.mainloop()
