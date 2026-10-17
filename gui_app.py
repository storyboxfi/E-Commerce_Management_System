import tkinter as tk
from tkinter import ttk, messagebox
import psycopg2
import db_core as core
from db_core import DATABASES


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Retail Ecosystem - Database Manager")
        self.geometry("980x520")
        top = ttk.Frame(self, padding=8); top.pack(fill="x")
        ttk.Label(top, text="Database:").pack(side="left")
        self.db_var = tk.StringVar(value="inventory_db")
        self.db_box = ttk.Combobox(top, textvariable=self.db_var, values=list(DATABASES), state="readonly", width=14)
        self.db_box.pack(side="left", padx=4)
        ttk.Label(top, text="Table:").pack(side="left", padx=(10, 0))
        self.tb_var = tk.StringVar()
        self.tb_box = ttk.Combobox(top, textvariable=self.tb_var, state="readonly", width=18)
        self.tb_box.pack(side="left", padx=4)
        for text, cmd in [("Refresh", self.refresh), ("Add", self.add), ("Edit", self.edit), ("Delete", self.delete)]:
            ttk.Button(top, text=text, command=cmd).pack(side="left", padx=3)
        self.db_box.bind("<<ComboboxSelected>>", lambda e: self.change_db())
        self.tb_box.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        self.tree = ttk.Treeview(self, show="headings")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True); sb.pack(side="left", fill="y")
        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, anchor="w").pack(side="bottom", fill="x")
        self.change_db()

    def change_db(self):
        tables = list(DATABASES[self.db_var.get()])
        self.tb_box["values"] = tables
        self.tb_var.set(tables[0])
        self.refresh()

    def meta(self):
        return DATABASES[self.db_var.get()][self.tb_var.get()]

    def guard(self, fn):
        try:
            fn()
            return True
        except psycopg2.Error as e:
            messagebox.showerror("Database error", str(e).strip())
            return False

    def refresh(self):
        def load():
            rows = core.fetch_table(self.db_var.get(), self.tb_var.get())
            self.tree.delete(*self.tree.get_children())
            cols = list(rows[0].keys()) if rows else [self.meta()["pk"]] + self.meta()["cols"]
            self.tree["columns"] = cols
            for c in cols:
                self.tree.heading(c, text=c); self.tree.column(c, width=110, anchor="w")
            for r in rows:
                self.tree.insert("", "end", values=[r[c] for c in cols])
            self.status.set(f"{self.db_var.get()}.{self.tb_var.get()} - {len(rows)} rows")
        self.guard(load)

    def selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Please select a row first."); return None
        cols = self.tree["columns"]
        return dict(zip(cols, self.tree.item(sel[0])["values"]))

    def form(self, title, initial=None):
        win = tk.Toplevel(self); win.title(title); win.grab_set()
        entries = {}
        for i, c in enumerate(self.meta()["cols"]):
            ttk.Label(win, text=c).grid(row=i, column=0, padx=8, pady=4, sticky="e")
            e = ttk.Entry(win, width=34); e.grid(row=i, column=1, padx=8, pady=4)
            if initial and initial.get(c) not in (None, "None"):
                e.insert(0, initial[c])
            entries[c] = e
        result = {}
        def ok():
            result.update({c: e.get().strip() for c, e in entries.items()}); win.destroy()
        ttk.Button(win, text="Save", command=ok).grid(row=len(entries), column=0, columnspan=2, pady=8)
        self.wait_window(win)
        return result

    def add(self):
        vals = self.form("Add row")
        if vals and self.guard(lambda: core.insert_row(self.db_var.get(), self.tb_var.get(), vals)):
            self.refresh()

    def edit(self):
        row = self.selected()
        if not row:
            return
        vals = self.form("Edit row", row)
        if vals and self.guard(lambda: core.update_row(self.db_var.get(), self.tb_var.get(), row[self.meta()["pk"]], vals)):
            self.refresh()

    def delete(self):
        row = self.selected()
        if row and messagebox.askyesno("Delete", f"Delete row {row[self.meta()['pk']]}?"):
            if self.guard(lambda: core.delete_row(self.db_var.get(), self.tb_var.get(), row[self.meta()["pk"]])):
                self.refresh()


if __name__ == "__main__":
    App().mainloop()
