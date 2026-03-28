import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path

from pdf_processor import convert_pdf_to_markdown


class PDFToMarkdownApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PDF to Markdown")
        self.root.geometry("1100x680")
        self.root.minsize(800, 500)

        self.pdf_files: list[str] = []
        self.markdown_content: dict[str, str] = {}
        self.current_file: str | None = None
        self._converting = False

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=10)
        main.grid(sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # ── Left panel ──────────────────────────────────────────────────
        left = ttk.LabelFrame(main, text="PDF Files", padding=6)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            left, selectmode="single", width=28,
            activestyle="none", font=("Helvetica", 11)
        )
        sb_list = ttk.Scrollbar(left, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb_list.set)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        sb_list.grid(row=0, column=1, sticky="ns")
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        btn_row = ttk.Frame(left)
        btn_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        ttk.Button(btn_row, text="Add PDF", command=self._add_pdf).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Remove", command=self._remove_pdf).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Convert All", command=self._convert_all).pack(side="left", padx=2)

        # ── Right panel ─────────────────────────────────────────────────
        right = ttk.LabelFrame(main, text="Markdown Preview", padding=6)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.preview = tk.Text(
            right, wrap="word", font=("Courier", 11),
            state="disabled", relief="flat", bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white", selectbackground="#264f78"
        )
        sb_prev = ttk.Scrollbar(right, orient="vertical", command=self.preview.yview)
        self.preview.configure(yscrollcommand=sb_prev.set)
        self.preview.grid(row=0, column=0, sticky="nsew")
        sb_prev.grid(row=0, column=1, sticky="ns")

        # ── Bottom bar ──────────────────────────────────────────────────
        bottom = ttk.Frame(main)
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self.status = ttk.Label(bottom, text="Ready  •  Add PDF files to get started.")
        self.status.pack(side="left")

        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=120)
        self.progress.pack(side="left", padx=10)

        ttk.Button(bottom, text="Save All", command=self._save_all).pack(side="right", padx=(6, 0))
        ttk.Button(bottom, text="Save Markdown", command=self._save_current).pack(side="right")

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------

    def _add_pdf(self):
        paths = filedialog.askopenfilenames(
            title="Select PDF files",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        added = 0
        for p in paths:
            if p not in self.pdf_files:
                self.pdf_files.append(p)
                self.listbox.insert("end", Path(p).name)
                added += 1
        if added:
            self._set_status(f"Added {added} file(s).")

    def _remove_pdf(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        path = self.pdf_files.pop(idx)
        self.listbox.delete(idx)
        self.markdown_content.pop(path, None)
        if self.current_file == path:
            self.current_file = None
            self._set_preview("")
        self._set_status("File removed.")

    def _on_select(self, _event=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        path = self.pdf_files[sel[0]]
        self.current_file = path
        if path in self.markdown_content:
            self._set_preview(self.markdown_content[path])
        else:
            self._set_preview("Not converted yet — click  Convert All.")

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _convert_all(self):
        if not self.pdf_files:
            messagebox.showwarning("No Files", "Add at least one PDF file first.")
            return
        if self._converting:
            return

        self._converting = True
        self.progress.start(12)
        total = len(self.pdf_files)

        def run():
            for i, path in enumerate(self.pdf_files, 1):
                name = Path(path).name
                self._set_status(f"Converting {i}/{total}: {name}")
                try:
                    md = convert_pdf_to_markdown(path)
                except Exception as exc:
                    md = f"> **Error converting file:** {exc}\n"
                self.markdown_content[path] = md
                if self.current_file == path:
                    self._set_preview(md)

            self._converting = False
            self.progress.stop()
            self._set_status(f"Done — {total} file(s) converted.")

        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def _save_current(self):
        if not self.current_file:
            messagebox.showwarning("No Selection", "Select a file in the list first.")
            return
        if self.current_file not in self.markdown_content:
            messagebox.showwarning("Not Converted", "Convert the file first.")
            return
        default = Path(self.current_file).stem + ".md"
        dest = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt")],
            initialfile=default,
            title="Save Markdown"
        )
        if dest:
            Path(dest).write_text(self.markdown_content[self.current_file], encoding="utf-8")
            self._set_status(f"Saved: {Path(dest).name}")

    def _save_all(self):
        if not self.markdown_content:
            messagebox.showwarning("Nothing to Save", "Convert files first.")
            return
        folder = filedialog.askdirectory(title="Select folder to save all Markdown files")
        if not folder:
            return
        folder = Path(folder)
        for path, content in self.markdown_content.items():
            out = folder / (Path(path).stem + ".md")
            out.write_text(content, encoding="utf-8")
        self._set_status(f"Saved {len(self.markdown_content)} file(s) to {folder.name}/")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str):
        self.status.config(text=msg)

    def _set_preview(self, text: str):
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFToMarkdownApp(root)
    root.mainloop()
