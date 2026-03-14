#!/usr/bin/env python3
# sistema_vendas.py
# Requisitos: Python 3.8+ (somente stdlib)
# Execute: python sistema_vendas.py

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sqlite3
from datetime import datetime
import csv
import os

DB_FILE = "vendas.db"

# ---------- Banco de dados ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS products (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  price REAL NOT NULL,
                  stock INTEGER NOT NULL
                 )""")
    c.execute("""CREATE TABLE IF NOT EXISTS sales (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT NOT NULL,
                  total REAL NOT NULL
                 )""")
    c.execute("""CREATE TABLE IF NOT EXISTS sale_items (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  sale_id INTEGER NOT NULL,
                  product_id INTEGER NOT NULL,
                  qty INTEGER NOT NULL,
                  price REAL NOT NULL,
                  FOREIGN KEY(sale_id) REFERENCES sales(id),
                  FOREIGN KEY(product_id) REFERENCES products(id)
                 )""")
    conn.commit()
    conn.close()

def add_product_db(name, price, stock):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", (name, price, stock))
    conn.commit()
    conn.close()

def edit_product_db(pid, name, price, stock):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE products SET name=?, price=?, stock=? WHERE id=?", (name, price, stock, pid))
    conn.commit()
    conn.close()

def delete_product_db(pid):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()

def get_products_db(search=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if search:
        like = f"%{search}%"
        c.execute("SELECT id, name, price, stock FROM products WHERE name LIKE ? ORDER BY name", (like,))
    else:
        c.execute("SELECT id, name, price, stock FROM products ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return rows

def get_product_by_id(pid):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, name, price, stock FROM products WHERE id=?", (pid,))
    row = c.fetchone()
    conn.close()
    return row

def create_sale_db(items, total):
    """items: list of dicts: {'product_id','qty','price'}"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    date = datetime.now().isoformat(timespec='seconds')
    c.execute("INSERT INTO sales (date, total) VALUES (?, ?)", (date, total))
    sale_id = c.lastrowid
    for it in items:
        c.execute("INSERT INTO sale_items (sale_id, product_id, qty, price) VALUES (?, ?, ?, ?)",
                  (sale_id, it['product_id'], it['qty'], it['price']))
        # update product stock
        c.execute("UPDATE products SET stock = stock - ? WHERE id=?", (it['qty'], it['product_id']))
    conn.commit()
    conn.close()
    return sale_id

def get_sales_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, date, total FROM sales ORDER BY date DESC")
    sales = c.fetchall()
    conn.close()
    return sales

def get_sale_items_db(sale_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""SELECT si.qty, si.price, p.name FROM sale_items si
                 JOIN products p ON p.id = si.product_id
                 WHERE si.sale_id = ?""", (sale_id,))
    items = c.fetchall()
    conn.close()
    return items

# ---------- Interface ----------
class SalesApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Vendas - Portfólio")
        self.geometry("1000x600")
        self.resizable(True, True)
        self.cart = []  # list of dicts: product_id, name, qty, price
        self.create_widgets()
        self.refresh_products()

    def create_widgets(self):
        # Frames
        left = ttk.Frame(self, padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right = ttk.Frame(self, padding=10)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Left: produto & busca
        search_frame = ttk.Frame(left)
        search_frame.pack(fill=tk.X, pady=(0,6))
        ttk.Label(search_frame, text="Buscar produto:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        search_entry.bind("<Return>", lambda e: self.refresh_products())
        ttk.Button(search_frame, text="Buscar", command=self.refresh_products).pack(side=tk.LEFT)

        prod_toolbar = ttk.Frame(left)
        prod_toolbar.pack(fill=tk.X, pady=(0,6))
        ttk.Button(prod_toolbar, text="Novo Produto", command=self.new_product).pack(side=tk.LEFT)
        ttk.Button(prod_toolbar, text="Editar Selecionado", command=self.edit_selected_product).pack(side=tk.LEFT, padx=6)
        ttk.Button(prod_toolbar, text="Excluir Selecionado", command=self.delete_selected_product).pack(side=tk.LEFT)

        # Treeview produtos
        cols = ("id","name","price","stock")
        self.prod_tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        self.prod_tree.heading("id", text="ID")
        self.prod_tree.heading("name", text="Nome")
        self.prod_tree.heading("price", text="Preço (R$)")
        self.prod_tree.heading("stock", text="Estoque")
        self.prod_tree.column("id", width=40, anchor=tk.CENTER)
        self.prod_tree.column("name", width=240)
        self.prod_tree.column("price", width=80, anchor=tk.E)
        self.prod_tree.column("stock", width=80, anchor=tk.CENTER)
        self.prod_tree.pack(fill=tk.BOTH, expand=True)

        # Add to cart
        add_frame = ttk.Frame(left, padding=(0,6))
        add_frame.pack(fill=tk.X)
        ttk.Label(add_frame, text="Qtd:").pack(side=tk.LEFT)
        self.qty_var = tk.IntVar(value=1)
        ttk.Entry(add_frame, width=5, textvariable=self.qty_var).pack(side=tk.LEFT, padx=6)
        ttk.Button(add_frame, text="Adicionar ao Carrinho", command=self.add_to_cart).pack(side=tk.LEFT)

        # Right: carrinho e checkout
        cart_label = ttk.Label(right, text="Carrinho", font=("TkDefaultFont", 12, "bold"))
        cart_label.pack(anchor=tk.W)

        self.cart_tree = ttk.Treeview(right, columns=("name","qty","price","subtotal"), show="headings")
        self.cart_tree.heading("name", text="Produto")
        self.cart_tree.heading("qty", text="Qtd")
        self.cart_tree.heading("price", text="Preço")
        self.cart_tree.heading("subtotal", text="Subtotal")
        self.cart_tree.column("qty", width=50, anchor=tk.CENTER)
        self.cart_tree.column("price", width=80, anchor=tk.E)
        self.cart_tree.column("subtotal", width=100, anchor=tk.E)
        self.cart_tree.pack(fill=tk.BOTH, expand=True)

        cart_actions = ttk.Frame(right, padding=(0,6))
        cart_actions.pack(fill=tk.X)
        ttk.Button(cart_actions, text="Remover Item", command=self.remove_cart_item).pack(side=tk.LEFT)
        ttk.Button(cart_actions, text="Limpar Carrinho", command=self.clear_cart).pack(side=tk.LEFT, padx=6)

        # Totais e checkout
        total_frame = ttk.Frame(right)
        total_frame.pack(fill=tk.X, pady=(6,0))
        ttk.Label(total_frame, text="Desconto (%):").pack(side=tk.LEFT)
        self.discount_var = tk.DoubleVar(value=0.0)
        ttk.Entry(total_frame, textvariable=self.discount_var, width=8).pack(side=tk.LEFT, padx=6)
        ttk.Button(total_frame, text="Finalizar Venda", command=self.checkout).pack(side=tk.RIGHT)
        self.total_label = ttk.Label(total_frame, text="Total: R$ 0.00", font=("TkDefaultFont", 11, "bold"))
        self.total_label.pack(side=tk.RIGHT, padx=12)

        # Bottom: histórico e export
        bottom = ttk.Frame(self, padding=10)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(bottom, text="Ver Histórico de Vendas", command=self.show_sales_history).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Exportar Histórico CSV", command=self.export_sales_csv).pack(side=tk.LEFT, padx=6)
        ttk.Button(bottom, text="Popular Exemplo (3 produtos)", command=self.populate_example).pack(side=tk.RIGHT)

    # ---------- Produtos ----------
    def refresh_products(self):
        search = self.search_var.get().strip()
        rows = get_products_db(search if search else None)
        for i in self.prod_tree.get_children():
            self.prod_tree.delete(i)
        for r in rows:
            pid, name, price, stock = r
            self.prod_tree.insert("", tk.END, values=(pid, name, f"{price:.2f}", stock))

    def new_product(self):
        dlg = ProductDialog(self, title="Novo Produto")
        self.wait_window(dlg)
        if dlg.result:
            name, price, stock = dlg.result
            add_product_db(name, price, stock)
            self.refresh_products()

    def edit_selected_product(self):
        sel = self.prod_tree.selection()
        if not sel:
            messagebox.showinfo("Editar", "Selecione um produto.")
            return
        pid = int(self.prod_tree.item(sel[0])['values'][0])
        row = get_product_by_id(pid)
        if not row:
            messagebox.showerror("Erro", "Produto não encontrado.")
            return
        dlg = ProductDialog(self, title="Editar Produto", default=(row[1], row[2], row[3]))
        self.wait_window(dlg)
        if dlg.result:
            name, price, stock = dlg.result
            edit_product_db(pid, name, price, stock)
            self.refresh_products()

    def delete_selected_product(self):
        sel = self.prod_tree.selection()
        if not sel:
            messagebox.showinfo("Excluir", "Selecione um produto.")
            return
        pid = int(self.prod_tree.item(sel[0])['values'][0])
        if messagebox.askyesno("Confirmar", "Deseja excluir o produto selecionado?"):
            delete_product_db(pid)
            self.refresh_products()

    # ---------- Carrinho ----------
    def add_to_cart(self):
        sel = self.prod_tree.selection()
        if not sel:
            messagebox.showinfo("Adicionar", "Selecione um produto para adicionar.")
            return
        pid = int(self.prod_tree.item(sel[0])['values'][0])
        prod = get_product_by_id(pid)
        if not prod:
            messagebox.showerror("Erro", "Produto não encontrado.")
            return
        _, name, price, stock = prod
        qty = int(self.qty_var.get() or 0)
        if qty <= 0:
            messagebox.showwarning("Quantidade", "Quantidade deve ser maior que 0.")
            return
        if qty > stock:
            messagebox.showwarning("Estoque", f"Estoque insuficiente ({stock} disponível).")
            return
        # se já estiver no carrinho, somar quantidade
        existing = next((it for it in self.cart if it['product_id']==pid), None)
        if existing:
            if existing['qty'] + qty > stock:
                messagebox.showwarning("Estoque", "Quantidade excede estoque.")
                return
            existing['qty'] += qty
        else:
            self.cart.append({"product_id": pid, "name": name, "qty": qty, "price": price})
        self.refresh_cart()

    def refresh_cart(self):
        for i in self.cart_tree.get_children():
            self.cart_tree.delete(i)
        total = 0.0
        for it in self.cart:
            subtotal = it['qty'] * it['price']
            total += subtotal
            self.cart_tree.insert("", tk.END, values=(it['name'], it['qty'], f"{it['price']:.2f}", f"{subtotal:.2f}"))
        discount_pct = max(0.0, min(100.0, self.discount_var.get() or 0.0))
        total_after = total * (1 - discount_pct/100)
        self.total_label.config(text=f"Total: R$ {total_after:.2f}")
        # store total in instance for checkout
        self._cart_total = total_after

    def remove_cart_item(self):
        sel = self.cart_tree.selection()
        if not sel:
            messagebox.showinfo("Remover", "Selecione um item no carrinho.")
            return
        name = self.cart_tree.item(sel[0])['values'][0]
        # find and remove first matching
        for idx, it in enumerate(self.cart):
            if it['name'] == name:
                del self.cart[idx]
                break
        self.refresh_cart()

    def clear_cart(self):
        if messagebox.askyesno("Limpar", "Limpar todo o carrinho?"):
            self.cart.clear()
            self.refresh_cart()

    # ---------- Checkout ----------
    def checkout(self):
        if not self.cart:
            messagebox.showinfo("Checkout", "Carrinho vazio.")
            return
        # Re-validate estoque before finalize (important)
        for it in self.cart:
            prod = get_product_by_id(it['product_id'])
            if not prod:
                messagebox.showerror("Erro", f"Produto {it['name']} não existe mais.")
                return
            if it['qty'] > prod[3]:
                messagebox.showerror("Estoque", f"Estoque insuficiente para {it['name']}. Disponível: {prod[3]}")
                return
        total = getattr(self, "_cart_total", None)
        if total is None:
            self.refresh_cart()
            total = getattr(self, "_cart_total", 0.0)
        if messagebox.askyesno("Confirmar Venda", f"Total da venda: R$ {total:.2f}\nConfirmar finalização?"):
            items = [{"product_id": it['product_id'], "qty": it['qty'], "price": it['price']} for it in self.cart]
            sale_id = create_sale_db(items, total)
            messagebox.showinfo("Venda Concluída", f"Venda registrada (ID: {sale_id}).")
            self.cart.clear()
            self.refresh_cart()
            self.refresh_products()

    # ---------- Histórico e export ----------
    def show_sales_history(self):
        dlg = SalesHistoryDialog(self)
        self.wait_window(dlg)

    def export_sales_csv(self):
        sales = get_sales_db()
        if not sales:
            messagebox.showinfo("Exportar", "Nenhuma venda para exportar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")], title="Salvar histórico")
        if not path:
            return
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["sale_id", "date", "total", "item_name", "qty", "unit_price"])
            for s in sales:
                sid, date, total = s
                items = get_sale_items_db(sid)
                for it in items:
                    qty, price, name = it
                    writer.writerow([sid, date, f"{total:.2f}", name, qty, f"{price:.2f}"])
        messagebox.showinfo("Exportado", f"Histórico exportado para:\n{path}")

    # ---------- Exemplo ----------
    def populate_example(self):
        # cria 3 produtos se não existirem
        existing = get_products_db()
        if existing:
            messagebox.showinfo("Popular", "Produtos já existem no banco.")
            return
        add_product_db("Caderno 100 folhas", 12.50, 20)
        add_product_db("Caneta Gel 0.7", 3.90, 50)
        add_product_db("Mochila Escolar", 89.90, 5)
        self.refresh_products()
        messagebox.showinfo("Popular", "3 produtos adicionados de exemplo.")

# ---------- Diálogos auxiliares ----------
class ProductDialog(tk.Toplevel):
    def __init__(self, parent, title="Produto", default=None):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.transient(parent)
        self.grab_set()
        ttk.Label(self, text="Nome:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=6)
        self.name_var = tk.StringVar(value=default[0] if default else "")
        ttk.Entry(self, textvariable=self.name_var, width=40).grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(self, text="Preço (R$):").grid(row=1, column=0, sticky=tk.W, padx=6, pady=6)
        self.price_var = tk.DoubleVar(value=default[1] if default else 0.0)
        ttk.Entry(self, textvariable=self.price_var).grid(row=1, column=1, padx=6, pady=6)
        ttk.Label(self, text="Estoque:").grid(row=2, column=0, sticky=tk.W, padx=6, pady=6)
        self.stock_var = tk.IntVar(value=default[2] if default else 0)
        ttk.Entry(self, textvariable=self.stock_var).grid(row=2, column=1, padx=6, pady=6)
        btns = ttk.Frame(self)
        btns.grid(row=3, column=0, columnspan=2, pady=8)
        ttk.Button(btns, text="Salvar", command=self.on_save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side=tk.LEFT)
        self.bind("<Return>", lambda e: self.on_save())

    def on_save(self):
        name = self.name_var.get().strip()
        try:
            price = float(self.price_var.get())
            stock = int(self.stock_var.get())
        except Exception:
            messagebox.showerror("Formato", "Preço ou estoque inválido.")
            return
        if not name:
            messagebox.showerror("Nome", "Nome não pode ser vazio.")
            return
        if price < 0 or stock < 0:
            messagebox.showerror("Valores", "Preço/estoque não podem ser negativos.")
            return
        self.result = (name, price, stock)
        self.destroy()

class SalesHistoryDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Histórico de Vendas")
        self.geometry("700x400")
        self.transient(parent)
        self.grab_set()
        top = ttk.Frame(self, padding=6)
        top.pack(fill=tk.X)
        ttk.Button(top, text="Atualizar", command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(top, text="Exportar CSV", command=parent.export_sales_csv).pack(side=tk.LEFT, padx=6)
        self.tree = ttk.Treeview(self, columns=("id","date","total"), show="headings")
        self.tree.heading("id", text="ID")
        self.tree.heading("date", text="Data")
        self.tree.heading("total", text="Total (R$)")
        self.tree.column("id", width=60, anchor=tk.CENTER)
        self.tree.column("date", width=260)
        self.tree.column("total", width=100, anchor=tk.E)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=6)
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="Detalhes", command=self.show_details).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Fechar", command=self.destroy).pack(side=tk.RIGHT)
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for s in get_sales_db():
            sid, date, total = s
            self.tree.insert("", tk.END, values=(sid, date, f"{total:.2f}"))

    def show_details(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Detalhes", "Selecione uma venda.")
            return
        sid = int(self.tree.item(sel[0])['values'][0])
        items = get_sale_items_db(sid)
        text = f"Venda ID: {sid}\n\n"
        for qty, price, name in items:
            text += f"{name} — {qty} x R$ {price:.2f} = R$ {qty*price:.2f}\n"
        messagebox.showinfo("Detalhes da Venda", text)

# ---------- Inicialização ----------
def main():
    init_db()
    app = SalesApp()
    app.mainloop()

if __name__ == "__main__":
    main()