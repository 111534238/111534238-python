import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import calendar
import json
import os
import csv

# ================= 引入 Matplotlib 繪圖套件 =================
# 注意：必須指定後端為 TkAgg，才能在 Tkinter 視窗中顯示圖表
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

# 設定 Matplotlib 字型以支援中文 (避免出現方塊亂碼)
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] 
plt.rcParams['axes.unicode_minus'] = False # 解決負號顯示問題

# 資料儲存檔名
DATA_FILE = "erp_v20_data.json"

# ================= 設定全域配色 (方便日後統一修改風格) =================
COLORS = {
    "primary": "#E45674",      # 主色調 (桃紅)
    "secondary": "#57606f",    # 次要色 (深灰)
    "success": "#2ecc71",      # 成功 (綠)
    "warning": "#ffa502",      # 警告 (橘)
    "danger": "#bd2323",       # 危險 (紅)
    "bg_light": "#f1f2f6",     # 淺灰背景
    "bg_white": "#ffffff",     # 純白背景
    "text": "#2f3542",         # 深色文字
    "table_head": "#dfe4ea",   # 表格標題底色
    "table_row_even": "#f1f2f6"# 表格偶數行底色
}

# 預設字型設定
FONT_MAIN = ("Microsoft JhengHei UI", 12)
FONT_BOLD = ("Microsoft JhengHei UI", 13, "bold")
FONT_TITLE = ("Microsoft JhengHei UI", 12, "bold")

# ================= 類別：輕量級月曆選擇器 =================
class SimpleCalendar(tk.Toplevel):
    """
    這是一個彈出式視窗，繼承自 Toplevel。
    用來讓使用者點選日期，並將選到的日期回傳給主視窗。
    """
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback  # 這是當使用者選好日期後，要執行的函式
        self.title("選擇日期")
        self.geometry("415x350")
        self.configure(bg=COLORS["bg_white"])
        self.current_date = datetime.date.today()
        self.setup_ui()

    def setup_ui(self):
        # 每次換月份時，先清空舊的按鈕
        for widget in self.winfo_children(): widget.destroy()
        
        # --- 頂部導航列 (上個月 / 顯示月份 / 下個月) ---
        header = tk.Frame(self, bg=COLORS["primary"], pady=5)
        header.pack(fill='x')
        
        btn_prev = tk.Button(header, text="<", command=lambda: self.change_month(-1),
                             bg=COLORS["primary"], fg="white", bd=0, font=FONT_BOLD, activebackground=COLORS["secondary"])
        btn_prev.pack(side='left', padx=15)
        
        tk.Label(header, text=self.current_date.strftime("%Y年 %m月"), 
                 font=("Microsoft JhengHei UI", 14, "bold"), bg=COLORS["primary"], fg="white").pack(side='left', expand=True)
        
        btn_next = tk.Button(header, text=">", command=lambda: self.change_month(1),
                             bg=COLORS["primary"], fg="white", bd=0, font=FONT_BOLD, activebackground=COLORS["secondary"])
        btn_next.pack(side='right', padx=15)

        # --- 星期標題 ---
        days_frame = tk.Frame(self, bg=COLORS["bg_light"], pady=5)
        days_frame.pack(fill='x')
        days = ["一", "二", "三", "四", "五", "六", "日"]
        for d in days: 
            tk.Label(days_frame, text=d, width=5, bg=COLORS["bg_light"], font=FONT_BOLD).pack(side='left', expand=True)

        # --- 日期按鈕區 ---
        cal_frame = tk.Frame(self, bg=COLORS["bg_white"], padx=10, pady=10)
        cal_frame.pack(expand=True, fill='both')
        
        # 使用 calendar 模組取得當月的週曆矩陣
        cal = calendar.monthcalendar(self.current_date.year, self.current_date.month)
        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day != 0: # 0 代表該格不屬於這個月份
                    btn = tk.Button(cal_frame, text=str(day), width=4, 
                                    command=lambda d=day: self.select_date(d),
                                    bg="white", relief="flat", font=FONT_MAIN)
                    # 加入滑鼠移入移出的變色效果
                    btn.bind("<Enter>", lambda e, b=btn: b.config(bg=COLORS["bg_light"]))
                    btn.bind("<Leave>", lambda e, b=btn: b.config(bg="white"))
                    btn.grid(row=r, column=c, padx=3, pady=3, ipady=3)

    def change_month(self, delta):
        """ 切換月份邏輯 """
        month = self.current_date.month + delta
        year = self.current_date.year
        if month > 12: month = 1; year += 1
        elif month < 1: month = 12; year -= 1
        self.current_date = self.current_date.replace(year=year, month=month, day=1)
        self.setup_ui()

    def select_date(self, day):
        """ 選擇日期後，格式化字串並呼叫 callback """
        selected_date = self.current_date.replace(day=day).strftime("%Y-%m-%d")
        self.callback(selected_date)
        self.destroy()

# ================= 類別：主系統邏輯 =================
class AdvancedERPSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("python238-倉庫庫存管理系統")
        self.root.geometry("1400x900")
        self.root.configure(bg=COLORS["bg_light"]) 
        
        # --- 註冊輸入驗證函式 (給 Entry 使用) ---
        self.vcmd_int = (self.root.register(self.validate_int), '%P')
        self.vcmd_float = (self.root.register(self.validate_float), '%P')

        self.setup_styles() # 設定 Treeview 與 Tab 樣式

        # --- 初始化資料結構 ---
        self.data = {
            "po_db": [],      # 採購單資料庫
            "stock_db": {'CPU-i9': 5, 'RAM-16G': 50}, # 現有庫存
            "sales_db": [],   # 銷售紀錄
            "ap_db": [],      # 應付帳款 (Accounts Payable)
            "memory_items": ['CPU-i9', 'RAM-16G', 'SSD-1TB', 'Office軟體'], # 選單記憶
            "memory_vendors": ['光華科技', '原價屋', '微軟經銷商'],
            "source_types": ['直接輸入', '採購計畫拋轉', '訂貨單拋轉', '詢價單轉入']
        }
        self.load_data() # 讀取 JSON
        self.create_main_layout() # 建立畫面
        
    # --- 輸入驗證工具 ---
    def validate_int(self, P):
        if P == "": return True
        if P.isdigit(): return True
        return False

    def validate_float(self, P):
        if P == "": return True
        try:
            val = float(P)
            if val >= 0: return True
        except ValueError:
            pass
        return False

    def setup_styles(self):
        """ 設定 Tkinter 樣式 (Treeview, Notebook 等) """
        style = ttk.Style()
        style.theme_use('clam') 

        # 分頁標籤樣式
        style.configure("TNotebook", background=COLORS["bg_light"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=[15, 8], font=("Microsoft JhengHei UI",15, "bold"), 
                        background="#dcdde1")
        style.map("TNotebook.Tab", background=[("selected", COLORS["primary"])], foreground=[("selected", "white")])

        # 表格樣式
        style.configure("Treeview", 
                        background="white",
                        foreground=COLORS["text"],
                        rowheight=40, 
                        fieldbackground="white",
                        font=FONT_MAIN,
                        borderwidth=0)
        
        style.configure("Treeview.Heading", 
                        font=FONT_BOLD, 
                        background=COLORS["table_head"], 
                        foreground=COLORS["text"],
                        relief="flat")
        
        style.map("Treeview", background=[('selected', COLORS["primary"])])

        style.configure("TFrame", background=COLORS["bg_light"])
        style.configure("TLabelframe", background=COLORS["bg_light"], borderwidth=1)
        style.configure("TLabelframe.Label", font=FONT_BOLD, background=COLORS["bg_light"], foreground=COLORS["primary"])

    def create_main_layout(self):
        """ 建立主畫面架構 """
        # 標題列
        title_frame = tk.Frame(self.root, bg=COLORS["primary"], height=60)
        title_frame.pack(fill='x', side='top')
        tk.Label(title_frame, text="🏢 倉庫庫存管理系統", 
                 font=("Microsoft JhengHei UI", 25, "bold"), 
                 bg=COLORS["primary"], fg="white").pack(side='left', padx=20, pady=10)

        # 建立分頁容器
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=20, pady=20)
        
        # 建立四個主要分頁
        self.tab_procure = ttk.Frame(self.notebook)
        self.tab_warehouse = ttk.Frame(self.notebook)
        self.tab_finance = ttk.Frame(self.notebook)
        self.tab_dashboard = ttk.Frame(self.notebook) 
        
        self.notebook.add(self.tab_procure, text=' 1. 採購日程管理 ')
        self.notebook.add(self.tab_warehouse, text=' 2. 進銷存管理 ')
        self.notebook.add(self.tab_finance, text=' 3. 應付帳款中心 ')
        self.notebook.add(self.tab_dashboard, text=' 4. 經營分析圖表 ')
        
        # 初始化各分頁內容
        self.setup_procure_tab()
        self.setup_warehouse_tab()
        self.setup_finance_tab()
        self.setup_dashboard_tab()
        
        # 綁定事件：切換分頁時刷新圖表
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)
        # 綁定事件：關閉視窗時存檔
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_flat_button(self, parent, text, cmd, bg_color, fg_color="white", icon=""):
        """ 快速建立扁平化設計按鈕的輔助函式 """
        btn = tk.Button(parent, text=f"{icon} {text}" if icon else text, 
                        command=cmd, bg=bg_color, fg=fg_color, 
                        font=FONT_BOLD, relief="flat", padx=15, pady=5, cursor="hand2")
        return btn

    def on_tab_change(self, event):
        # 如果切換到圖表頁，自動刷新數據
        if self.notebook.select() == str(self.tab_dashboard):
            self.refresh_dashboard()

    # ================= 檔案存取邏輯 (JSON) =================
    def save_data(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"存檔錯誤: {e}")

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # 資料庫遷移與預設值補丁 (防止舊版資料缺欄位報錯)
                    if 'sales_db' not in loaded: loaded['sales_db'] = []
                    for p in loaded.get('po_db', []):
                        if 'received_qty' not in p: p['received_qty'] = 0
                        if 'delivery_date' not in p: p['delivery_date'] = datetime.datetime.now().strftime('%Y-%m-%d')
                        if 'mfg_date' not in p: p['mfg_date'] = ''
                        if 'email_status' not in p: p['email_status'] = '未傳送'
                        if 'source' not in p: p['source'] = '直接輸入'
                    for a in loaded.get('ap_db', []):
                        if 'status' not in a: a['status'] = 'Unpaid'
                    for s in loaded.get('sales_db', []):
                        if 'price' not in s: s['price'] = 0
                        if 'total' not in s: s['total'] = 0
                    self.data.update(loaded)
            except Exception as e:
                print(f"讀取錯誤: {e}")

    def on_close(self):
        if messagebox.askokcancel("離開", "確定離開？(資料將自動儲存)"):
            self.save_data()
            self.root.destroy()

    def get_id(self, prefix):
        """ 產生唯一的單號 (格式: 前綴-月日時分秒) """
        return f"{prefix}-{datetime.datetime.now().strftime('%m%H%M%S')}"

    # ================= Tab 1: 採購管理 =================
    def setup_procure_tab(self):
        frame_top = tk.Frame(self.tab_procure, bg="white", pady=15, padx=15)
        frame_top.pack(fill='x', padx=10, pady=10)
        
        # 頂部功能按鈕區
        self.create_flat_button(frame_top, "查看日程表", self.show_calendar_view, COLORS["secondary"], icon="📅").pack(side='left', padx=5)
        self.create_flat_button(frame_top, "匯出報表", self.export_procurement_data, "#27ae60", icon="📊").pack(side='left', padx=5)

        self.create_flat_button(frame_top, "修改", lambda: self.open_po_window(is_edit=True), COLORS["bg_light"], fg_color=COLORS["text"], icon="✏️").pack(side='right', padx=5)
        self.create_flat_button(frame_top, "刪除", self.delete_po, COLORS["danger"], icon="🗑️").pack(side='right', padx=5)
        self.create_flat_button(frame_top, "Email傳送", self.send_email_simulation, COLORS["warning"], icon="📧").pack(side='right', padx=5)
        self.create_flat_button(frame_top, "新增採購單", self.open_po_window, COLORS["primary"], icon="➕").pack(side='right', padx=5)

        # 建立 Treeview (採購列表)
        cols = ("單號", "來源", "廠商", "品項", "製造日期", "訂購量", "預計交期", "郵件狀態", "總金額", "進貨狀態")
        self.tree_po = ttk.Treeview(self.tab_procure, columns=cols, show='headings', height=15)
        
        widths = [120, 100, 120, 120, 100, 70, 100, 100, 80, 100]
        for c, w in zip(cols, widths):
            self.tree_po.heading(c, text=c)
            self.tree_po.column(c, width=w, anchor='center')
        
        # 設定特殊狀態的顏色 (已結案變灰，部分交貨變紅)
        self.tree_po.tag_configure('closed', foreground='#bdc3c7') 
        self.tree_po.tag_configure('partial', foreground=COLORS["primary"]) 
        self.tree_po.tag_configure('even', background=COLORS["table_row_even"]) 
        
        self.tree_po.pack(fill='both', expand=True, padx=10, pady=(0,10))
        self.refresh_po_list()

    def refresh_po_list(self):
        """ 刷新採購列表數據 """
        for row in self.tree_po.get_children(): self.tree_po.delete(row)
        for idx, p in enumerate(self.data['po_db']):
            total = p['qty'] * p['price']
            status_show = p['status']
            tag = 'odd' if idx % 2 != 0 else 'even'
            
            # 判斷狀態顯示文字
            if p['status'] == 'Open' and p['received_qty'] > 0:
                status_show = f"部分 ({p['received_qty']}/{p['qty']})"
                tag_special = 'partial'
            elif p['status'] == 'Closed':
                tag_special = 'closed'
            else:
                tag_special = 'open'
            
            mfg_date = p.get('mfg_date', '')

            self.tree_po.insert("", "end", iid=idx, values=(
                p['id'], p['source'], p['vendor'], p['item'], mfg_date,
                p['qty'], p['delivery_date'], p['email_status'], total, status_show
            ), tags=(tag, tag_special))

    def export_procurement_data(self):
        """ 匯出 CSV 功能 """
        if not self.data['po_db']:
            messagebox.showwarning("無資料", "目前沒有採購單可以匯出！")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Excel CSV 檔案", "*.csv"), ("所有檔案", "*.*")],
            title="匯出採購報表"
        )
        if not filename: return 

        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["單號", "來源單據", "廠商", "品項", "製造日期", "訂購數量", "預計單價", "總金額", "預計交期", "已收數量", "狀態"])
                for p in self.data['po_db']:
                    writer.writerow([
                        p['id'], p['source'], p['vendor'], p['item'], p.get('mfg_date', ''),
                        p['qty'], p['price'], p['qty']*p['price'], 
                        p['delivery_date'], p['received_qty'], p['status']
                    ])
            messagebox.showinfo("匯出成功", f"檔案已成功儲存至：\n{filename}")
        except Exception as e:
            messagebox.showerror("匯出失敗", f"發生錯誤：{str(e)}")

    def open_po_window(self, is_edit=False):
        """ 彈出新增/修改採購單的視窗 """
        edit_idx, edit_val = None, None
        if is_edit:
            sel = self.tree_po.selection()
            if not sel: return
            edit_idx = int(sel[0])
            edit_val = self.data['po_db'][edit_idx]
            if edit_val['status'] == 'Closed': return messagebox.showwarning("鎖定", "已結案無法修改")

        win = tk.Toplevel(self.root)
        win.title("修改採購單" if is_edit else "新增採購單")
        win.geometry("500x650")
        win.configure(bg="white")
        
        form = tk.Frame(win, padx=30, pady=30, bg="white")
        form.pack(fill='both', expand=True)

        # 輔助函式：快速建立標籤與輸入框
        def add_field(label, row, widget_class, **kwargs):
            tk.Label(form, text=label, font=FONT_BOLD, bg="white", fg=COLORS["secondary"]).grid(row=row, column=0, sticky='w', pady=10)
            w = widget_class(form, font=FONT_MAIN, **kwargs)
            w.grid(row=row, column=1, sticky='ew', padx=10)
            return w

        # --- 表單欄位 ---
        e_id = add_field("單號:", 0, tk.Entry, bg="#f1f2f6", relief="flat")
        e_id.insert(0, edit_val['id'] if is_edit else self.get_id("PO"))
        e_id.config(state='readonly')

        tk.Label(form, text="來源單據:", font=FONT_BOLD, bg="white", fg=COLORS["secondary"]).grid(row=1, column=0, sticky='w')
        cb_source = ttk.Combobox(form, values=self.data['source_types'], state='readonly', font=FONT_MAIN)
        cb_source.set(edit_val['source'] if is_edit else '直接輸入')
        cb_source.grid(row=1, column=1, sticky='ew', padx=10)

        tk.Label(form, text="廠商:", font=FONT_BOLD, bg="white", fg=COLORS["secondary"]).grid(row=2, column=0, sticky='w')
        cb_vendor = ttk.Combobox(form, values=self.data['memory_vendors'], font=FONT_MAIN)
        if is_edit: cb_vendor.set(edit_val['vendor'])
        cb_vendor.grid(row=2, column=1, sticky='ew', padx=10)

        tk.Label(form, text="品項:", font=FONT_BOLD, bg="white", fg=COLORS["secondary"]).grid(row=3, column=0, sticky='w')
        cb_item = ttk.Combobox(form, values=self.data['memory_items'], font=FONT_MAIN)
        if is_edit: cb_item.set(edit_val['item'])
        cb_item.grid(row=3, column=1, sticky='ew', padx=10)

        tk.Label(form, text="製造日期:", font=FONT_BOLD, bg="white", fg=COLORS["secondary"]).grid(row=4, column=0, sticky='w')
        mfg_frame = tk.Frame(form, bg="white")
        mfg_frame.grid(row=4, column=1, sticky='ew', padx=10)
        e_mfg = tk.Entry(mfg_frame, font=FONT_MAIN, bg="#f1f2f6", relief="flat")
        e_mfg.pack(side='left', fill='x', expand=True)
        if is_edit: e_mfg.insert(0, edit_val.get('mfg_date', ''))
        
        # 日期選擇器按鈕
        tk.Button(mfg_frame, text="📅", command=lambda: SimpleCalendar(win, lambda d: (e_mfg.delete(0, 'end'), e_mfg.insert(0, d))),
                  relief="flat", bg=COLORS["secondary"], fg="white").pack(side='right', padx=2)

        e_qty = add_field("數量:", 5, tk.Entry, bg="#f1f2f6", relief="flat", validate="key", validatecommand=self.vcmd_int)
        if is_edit: e_qty.insert(0, edit_val['qty'])

        e_price = add_field("預計單價:", 6, tk.Entry, bg="#f1f2f6", relief="flat", validate="key", validatecommand=self.vcmd_float)
        if is_edit: e_price.insert(0, edit_val['price'])

        tk.Label(form, text="預計交期:", font=FONT_BOLD, bg="white", fg=COLORS["secondary"]).grid(row=7, column=0, sticky='w')
        date_frame = tk.Frame(form, bg="white")
        date_frame.grid(row=7, column=1, sticky='ew', padx=10)
        e_date = tk.Entry(date_frame, font=FONT_MAIN, bg="#f1f2f6", relief="flat")
        e_date.pack(side='left', fill='x', expand=True)
        e_date.insert(0, edit_val['delivery_date'] if is_edit else datetime.datetime.now().strftime('%Y-%m-%d'))
        
        tk.Button(date_frame, text="📅", command=lambda: SimpleCalendar(win, lambda d: (e_date.delete(0, 'end'), e_date.insert(0, d))),
                  relief="flat", bg=COLORS["secondary"], fg="white").pack(side='right', padx=2)

        def save():
            raw_vendor = cb_vendor.get().strip()
            raw_item = cb_item.get().strip()
            raw_qty = e_qty.get().strip()
            raw_price = e_price.get().strip()
            raw_date = e_date.get().strip()
            raw_mfg = e_mfg.get().strip()

            if not raw_vendor or not raw_item or not raw_qty or not raw_price or not raw_date:
                messagebox.showwarning("資料不完整", "請注意：除了製造日期外，所有欄位都必須填寫！")
                return

            try:
                qty_val = int(raw_qty)
                price_val = float(raw_price)
            except ValueError:
                messagebox.showerror("格式錯誤", "數量與單價格式不正確")
                return

            if qty_val <= 0:
                messagebox.showerror("數值錯誤", "數量必須大於 0！")
                return

            data = {
                'id': e_id.get(),
                'source': cb_source.get(),
                'vendor': raw_vendor,
                'item': raw_item,
                'mfg_date': raw_mfg,
                'qty': qty_val,
                'price': price_val,
                'delivery_date': raw_date,
                'received_qty': edit_val['received_qty'] if is_edit else 0,
                'email_status': edit_val['email_status'] if is_edit else '未傳送',
                'status': 'Open'
            }
            
            # 自動將新輸入的廠商與品項加入記憶清單
            if data['vendor'] not in self.data['memory_vendors']: self.data['memory_vendors'].append(data['vendor'])
            if data['item'] not in self.data['memory_items']: self.data['memory_items'].append(data['item'])
            
            if is_edit: self.data['po_db'][edit_idx] = data
            else: self.data['po_db'].append(data)
            
            self.save_data()
            self.refresh_po_list()
            self.refresh_warehouse_list()
            win.destroy()
            
            if not is_edit:
                messagebox.showinfo("成功", "採購單已建立！")

        self.create_flat_button(form, "儲存並建立", save, COLORS["success"]).grid(row=8, column=0, columnspan=2, pady=30, sticky='ew')

    def send_email_simulation(self):
        """ 模擬發送 Email """
        sel = self.tree_po.selection()
        if not sel: return messagebox.showwarning("提示", "請選擇要傳送的採購單")
        idx = int(sel[0])
        po = self.data['po_db'][idx]
        messagebox.showinfo("傳送成功", f"採購單 {po['id']} 已透過 Email 發送給 {po['vendor']}！")
        po['email_status'] = '已傳送 (廠商未讀)'
        self.refresh_po_list()
        self.save_data()
        
        # 模擬廠商讀取 (用對話框詢問)
        if messagebox.askyesno("確認", "廠商已讀取郵件？"):
            po['email_status'] = '✅ 廠商已讀'
            self.refresh_po_list()
            self.save_data()

    def delete_po(self):
        """ 刪除採購單 (有防呆：已進貨不能刪) """
        sel = self.tree_po.selection()
        if not sel: return
        idx = int(sel[0])
        if self.data['po_db'][idx]['status'] != 'Open' or self.data['po_db'][idx]['received_qty'] > 0:
            return messagebox.showerror("禁止", "已有進貨紀錄或已結案，無法刪除。")
        del self.data['po_db'][idx]
        self.refresh_po_list()
        self.save_data()

    def show_calendar_view(self):
        """ 顯示簡單的採購交期列表視窗 """
        win = tk.Toplevel(self.root)
        win.title("採購日程表 (本月)")
        win.geometry("600x450")
        win.configure(bg="white")
        tree = ttk.Treeview(win, columns=("交期", "廠商", "品項", "未交數量"), show='headings')
        tree.heading("交期", text="預計交期"); tree.column("交期", width=120, anchor="center")
        tree.heading("廠商", text="廠商"); tree.column("廠商", width=120, anchor="center")
        tree.heading("品項", text="品項"); tree.column("品項", width=150, anchor="center")
        tree.heading("未交數量", text="未交數量"); tree.column("未交數量", width=80, anchor="center")
        tree.pack(fill='both', expand=True, padx=10, pady=10)
        sorted_po = sorted(self.data['po_db'], key=lambda x: x['delivery_date'])
        for i, p in enumerate(sorted_po):
            if p['status'] == 'Open':
                remain = p['qty'] - p['received_qty']
                tag = 'even' if i % 2 == 0 else 'odd'
                tree.insert("", "end", values=(p['delivery_date'], p['vendor'], p['item'], remain), tags=(tag,))
        tree.tag_configure('even', background=COLORS["table_row_even"])

    # ================= Tab 2: 倉儲管理 (進銷存) =================
    def setup_warehouse_tab(self):
        # 使用 PanedWindow 建立左右可調整大小的分欄
        paned = ttk.PanedWindow(self.tab_warehouse, orient=tk.HORIZONTAL)
        paned.pack(fill='both', expand=True, padx=10, pady=10)
        
        # --- 左側：待進貨監控 ---
        frame_l = ttk.LabelFrame(paned, text="📦 待進貨監控", padding=10)
        paned.add(frame_l, weight=2)
        cols = ("單號", "品項", "訂購量", "已收量", "尚欠量", "狀態")
        self.tree_in = ttk.Treeview(frame_l, columns=cols, show='headings')
        for c in cols: 
            self.tree_in.heading(c, text=c)
            if c == "單號": w = 130  
            else: w = 80
            self.tree_in.column(c, anchor='center', width=w)
        self.tree_in.pack(fill='both', expand=True)
        # 綁定雙擊事件 -> 開啟收貨視窗
        self.tree_in.bind("<Double-1>", self.open_receipt_window)
        self.tree_in.tag_configure('even', background=COLORS["table_row_even"])
        
        # --- 右側：現有庫存 ---
        frame_r = ttk.LabelFrame(paned, text="📊 庫存與銷貨", padding=10)
        paned.add(frame_r, weight=2)
        self.tree_stock = ttk.Treeview(frame_r, columns=("品項", "庫存量", "庫存總值"), show='headings')
        self.tree_stock.heading("品項", text="品項"); self.tree_stock.column("品項", width=100, anchor='center')
        self.tree_stock.heading("庫存量", text="庫存量"); self.tree_stock.column("庫存量", width=80, anchor='center')
        self.tree_stock.heading("庫存總值", text="庫存總值($)"); self.tree_stock.column("庫存總值", width=100, anchor='center')
        
        self.tree_stock.pack(fill='both', expand=True)
        self.tree_stock.tag_configure('even', background=COLORS["table_row_even"])
        
        # 銷貨按鈕
        self.create_flat_button(frame_r, "銷貨/領料出庫 (紀錄營收)", self.open_sales_window, COLORS["danger"], icon="📤").pack(fill='x', pady=10)

        self.refresh_warehouse_list()

    def get_latest_price(self, item_name):
        """ 取得該品項最近一次的採購單價 (用於計算庫存成本) """
        related_pos = [p for p in self.data['po_db'] if p['item'] == item_name]
        if not related_pos:
            return 0 
        return related_pos[-1]['price']

    def refresh_warehouse_list(self):
        """ 刷新待進貨與庫存列表 """
        # 1. 刷新待進貨清單 (只顯示 Status = Open 的)
        for row in self.tree_in.get_children(): self.tree_in.delete(row)
        idx = 0
        for p in self.data['po_db']:
            if p['status'] == 'Open':
                remain = p['qty'] - p['received_qty']
                status_txt = "等待交貨" if p['received_qty'] == 0 else "部分交貨"
                tag = 'even' if idx % 2 == 0 else 'odd'
                self.tree_in.insert("", "end", values=(p['id'], p['item'], p['qty'], p['received_qty'], remain, status_txt), tags=(tag,))
                idx += 1

        # 2. 刷新庫存清單 (從 stock_db 讀取)
        for row in self.tree_stock.get_children(): self.tree_stock.delete(row)
        idx = 0
        for k, qty in self.data['stock_db'].items():
            tag = 'even' if idx % 2 == 0 else 'odd'
            price = self.get_latest_price(k)
            total_val = qty * price
            
            self.tree_stock.insert("", "end", values=(k, qty, f"${total_val:,.0f}"), tags=(tag,))
            idx += 1

    def open_receipt_window(self, event):
        """ 進貨驗收視窗 (點擊待進貨單據後觸發) """
        sel = self.tree_in.selection()
        if not sel: return
        po_id = self.tree_in.item(sel, 'values')[0]
        # 找到原始採購單數據
        target_idx = next((i for i, p in enumerate(self.data['po_db']) if p['id'] == po_id), None)
        target_po = self.data['po_db'][target_idx]
        remain = target_po['qty'] - target_po['received_qty']

        win = tk.Toplevel(self.root)
        win.title(f"進貨驗收 - {target_po['item']}")
        win.geometry("350x400")
        win.configure(bg="white")
        
        tk.Label(win, text=f"尚欠數量: {remain}", fg=COLORS["danger"], font=("Microsoft JhengHei UI", 14, "bold"), bg="white").pack(pady=20)
        
        f = tk.Frame(win, bg="white"); f.pack(fill='x', padx=30)
        
        tk.Label(f, text="本次實收數量:", font=FONT_BOLD, bg="white").pack(anchor='w')
        e_qty = tk.Entry(f, font=FONT_MAIN, bg="#f1f2f6", relief="flat", justify='center', validate="key", validatecommand=self.vcmd_int)
        e_qty.insert(0, remain)
        e_qty.pack(fill='x', pady=5)
        
        tk.Label(f, text="發票金額 (成本):", font=FONT_BOLD, bg="white").pack(anchor='w', pady=(10,0))
        e_amt = tk.Entry(f, font=FONT_MAIN, bg="#f1f2f6", relief="flat", justify='center', validate="key", validatecommand=self.vcmd_float)
        e_amt.insert(0, remain * target_po['price']) 
        e_amt.pack(fill='x', pady=5)

        # 自動計算金額 (數量 x 單價)
        def auto_calc(event):
            try:
                current_qty = e_qty.get()
                if not current_qty: return 
                qty = int(current_qty)
                price = target_po['price']
                total = qty * price
                e_amt.delete(0, 'end') 
                e_amt.insert(0, str(total))
            except ValueError:
                pass

        e_qty.bind("<KeyRelease>", auto_calc)

        def confirm():
            """ 確認收貨的核心邏輯 """
            try:
                qty_in = int(e_qty.get())
                amt_in = float(e_amt.get())
                if qty_in > remain:
                    if not messagebox.askyesno("警告", "輸入數量大於訂購殘量，確定超收？"): return

                # 1. 更新採購單狀態
                target_po['received_qty'] += qty_in
                if target_po['received_qty'] >= target_po['qty']:
                    target_po['status'] = 'Closed'
                
                # 2. 增加庫存
                item = target_po['item']
                self.data['stock_db'][item] = self.data['stock_db'].get(item, 0) + qty_in
                
                # 3. 產生應付帳款 (AP)
                self.data['ap_db'].append({
                    'id': self.get_id("AP"),
                    'po_ref': target_po['id'],
                    'date': datetime.datetime.now().strftime("%Y-%m-%d"),
                    'vendor': target_po['vendor'],
                    'desc': f"進貨 {item} x{qty_in}",
                    'amt': amt_in,
                    'status': 'Unpaid'
                })
                
                self.save_data()
                self.refresh_warehouse_list()
                self.refresh_po_list()
                self.refresh_finance_list()
                win.destroy()
                messagebox.showinfo("成功", "已入庫並產生應付帳款單！")
            except ValueError:
                messagebox.showerror("錯誤", "數字格式錯誤")
        
        self.create_flat_button(win, "確認入庫", confirm, COLORS["success"], icon="✅").pack(pady=30, fill='x', padx=30)

    def open_sales_window(self):
        """ 銷貨/出庫視窗 """
        win = tk.Toplevel(self.root)
        win.title("銷貨/出庫單")
        win.geometry("350x450")
        win.configure(bg="white")
        
        f = tk.Frame(win, bg="white", padx=30, pady=20); f.pack(fill='both')

        tk.Label(f, text="選擇品項:", font=FONT_BOLD, bg="white").pack(anchor='w')
        items = list(self.data['stock_db'].keys())
        cb_item = ttk.Combobox(f, values=items, font=FONT_MAIN)
        cb_item.pack(fill='x', pady=5)
        
        tk.Label(f, text="出庫數量:", font=FONT_BOLD, bg="white").pack(anchor='w', pady=(10,0))
        e_qty = tk.Entry(f, font=FONT_MAIN, bg="#f1f2f6", relief="flat", validate="key", validatecommand=self.vcmd_int); 
        e_qty.pack(fill='x', pady=5)

        tk.Label(f, text="銷售單價 (收入):", font=FONT_BOLD, bg="white").pack(anchor='w', pady=(10,0))
        e_price = tk.Entry(f, font=FONT_MAIN, bg="#f1f2f6", relief="flat", validate="key", validatecommand=self.vcmd_float); 
        e_price.pack(fill='x', pady=5)
        e_price.insert(0, "0")
        
        tk.Label(f, text="日期:", font=FONT_BOLD, bg="white").pack(anchor='w', pady=(10,0))
        d_frame = tk.Frame(f, bg="white")
        d_frame.pack(fill='x', pady=5)
        e_date = tk.Entry(d_frame, width=15, font=FONT_MAIN, bg="#f1f2f6", relief="flat")
        e_date.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))
        e_date.pack(side='left', fill='x', expand=True)
        tk.Button(d_frame, text="📅", command=lambda: SimpleCalendar(win, lambda d: (e_date.delete(0,'end'), e_date.insert(0,d))),
                  relief="flat", bg=COLORS["secondary"], fg="white").pack(side='left', padx=5)

        def confirm_sales():
            item = cb_item.get()
            try:
                qty = int(e_qty.get())
                price = float(e_price.get())
                current_stock = self.data['stock_db'].get(item, 0)
                
                # 檢查庫存是否足夠
                if qty > current_stock:
                    return messagebox.showerror("錯誤", f"庫存不足！目前只有 {current_stock}")
                
                # 扣庫存 & 增加銷售紀錄
                self.data['stock_db'][item] -= qty
                self.data['sales_db'].append({
                    'date': e_date.get(),
                    'item': item,
                    'qty': qty,
                    'price': price,
                    'total': qty * price
                })
                self.save_data()
                self.refresh_warehouse_list()
                win.destroy()
                messagebox.showinfo("成功", f"出庫完成，營收增加 ${qty*price}")
            except ValueError:
                messagebox.showerror("錯誤", "數量或價格格式錯誤")

        self.create_flat_button(win, "確認出庫", confirm_sales, COLORS["danger"], icon="📤").pack(side='bottom', fill='x', padx=30, pady=30)

    # ================= Tab 3: 財務管理 =================
    def setup_finance_tab(self):
        # 內部分頁：待付款 vs 已付款
        sub_notebook = ttk.Notebook(self.tab_finance)
        sub_notebook.pack(fill='both', expand=True, padx=10, pady=10)
        self.frame_unpaid = ttk.Frame(sub_notebook)
        self.frame_paid = ttk.Frame(sub_notebook)
        sub_notebook.add(self.frame_unpaid, text=' 🔴 待付款 (應付帳款) ')
        sub_notebook.add(self.frame_paid, text=' 🟢 已付款紀錄 ')
        
        self.tree_unpaid = ttk.Treeview(self.frame_unpaid, columns=("單號", "日期", "廠商", "摘要", "金額"), show='headings')
        for c in ("單號", "日期", "廠商", "摘要", "金額"): 
            self.tree_unpaid.heading(c, text=c); self.tree_unpaid.column(c, anchor='center')
        self.tree_unpaid.pack(fill='both', expand=True, padx=5, pady=5)
        self.tree_unpaid.tag_configure('even', background=COLORS["table_row_even"])
        
        self.create_flat_button(self.frame_unpaid, "付款確認", self.process_payment, COLORS["warning"], icon="💰").pack(pady=10)
        
        self.tree_paid = ttk.Treeview(self.frame_paid, columns=("單號", "付款日期", "廠商", "摘要", "金額"), show='headings')
        for c in ("單號", "付款日期", "廠商", "摘要", "金額"): 
            self.tree_paid.heading(c, text=c); self.tree_paid.column(c, anchor='center')
        self.tree_paid.pack(fill='both', expand=True, padx=5, pady=5)
        self.tree_paid.tag_configure('even', background=COLORS["table_row_even"])
        
        self.refresh_finance_list()

    def refresh_finance_list(self):
        """ 根據付款狀態分類顯示 AP """
        for row in self.tree_unpaid.get_children(): self.tree_unpaid.delete(row)
        for row in self.tree_paid.get_children(): self.tree_paid.delete(row)
        
        idx_u, idx_p = 0, 0
        for a in self.data['ap_db']:
            if a['status'] == 'Unpaid':
                tag = 'even' if idx_u % 2 == 0 else 'odd'
                self.tree_unpaid.insert("", "end", values=(a['id'], a['date'], a['vendor'], a['desc'], a['amt']), tags=(tag,))
                idx_u += 1
            else:
                tag = 'even' if idx_p % 2 == 0 else 'odd'
                self.tree_paid.insert("", "end", values=(a['id'], a.get('pay_date', '-'), a['vendor'], a['desc'], a['amt']), tags=(tag,))
                idx_p += 1

    def process_payment(self):
        """ 執行付款動作 """
        sel = self.tree_unpaid.selection()
        if not sel: return messagebox.showwarning("提示", "請選擇一筆帳款")
        item_vals = self.tree_unpaid.item(sel, 'values')
        ap_id = item_vals[0]
        if messagebox.askyesno("付款確認", f"確定支付 {ap_id} 金額 ${item_vals[4]}？"):
            for a in self.data['ap_db']:
                if a['id'] == ap_id:
                    a['status'] = 'Paid'
                    a['pay_date'] = datetime.datetime.now().strftime("%Y-%m-%d")
                    break
            self.save_data()
            self.refresh_finance_list()
            messagebox.showinfo("成功", "付款完成")

    # ================= Tab 4: 經營分析 (Matplotlib + 列表) =================
    def setup_dashboard_tab(self):
        control_frame = tk.Frame(self.tab_dashboard, pady=15, bg=COLORS["bg_light"])
        control_frame.pack(fill='x')
        
        tk.Label(control_frame, text="選擇統計月份:", font=FONT_BOLD, bg=COLORS["bg_light"]).pack(side='left', padx=15)
        
        # 產生最近 12 個月的選單
        months = []
        d = datetime.date.today()
        for i in range(12):
            months.append(d.strftime("%Y-%m"))
            d = d.replace(day=1) - datetime.timedelta(days=1)
        
        self.dash_month_var = tk.StringVar(value=months[0])
        cb_month = ttk.Combobox(control_frame, textvariable=self.dash_month_var, values=months, width=12, font=FONT_MAIN)
        cb_month.pack(side='left')
        
        self.create_flat_button(control_frame, "刷新報表", self.refresh_dashboard, COLORS["secondary"], icon="🔄").pack(side='left', padx=15)

        # 建立圖表分頁
        self.dash_notebook = ttk.Notebook(self.tab_dashboard)
        self.dash_notebook.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.page_overview = ttk.Frame(self.dash_notebook)
        self.page_trends = ttk.Frame(self.dash_notebook)
        self.page_individual = ttk.Frame(self.dash_notebook)
        self.page_cost_rev = ttk.Frame(self.dash_notebook)
        self.page_list = ttk.Frame(self.dash_notebook) 
        
        self.dash_notebook.add(self.page_overview, text=' 1. 銷售佔比') 
        self.dash_notebook.add(self.page_trends, text=' 2. 進銷趨勢')
        self.dash_notebook.add(self.page_individual, text=' 3. 單品個別分析')
        self.dash_notebook.add(self.page_cost_rev, text=' 4. 成本與收入')
        self.dash_notebook.add(self.page_list, text=' 5. 庫存狀態列表') 

        self.init_list_page() 

    def clear_canvas(self, parent_frame):
        """ 清除畫布上的舊圖表 """
        for widget in parent_frame.winfo_children():
            widget.destroy()

    def embed_chart(self, parent_frame, figure):
        """ 將 Matplotlib Figure 嵌入 Tkinter Frame """
        canvas = FigureCanvasTkAgg(figure, master=parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    def refresh_dashboard(self):
        """ 統籌刷新所有圖表 """
        target_month = self.dash_month_var.get()
        
        self.clear_canvas(self.page_overview)
        self.plot_overview_pie(self.page_overview, target_month)
        
        self.clear_canvas(self.page_trends)
        self.plot_trend_line(self.page_trends)

        self.setup_individual_analysis(self.page_individual)

        self.clear_canvas(self.page_cost_rev)
        self.plot_financial_bar(self.page_cost_rev, target_month)
        
        self.update_list_page()

    # --- Chart 1: 圓餅圖 (每月銷售佔比) ---
    def plot_overview_pie(self, parent, month):
        # 統計該月份的銷售數據
        sales_stats = {}
        for s in self.data['sales_db']:
            if s['date'].startswith(month):
                sales_stats[s['item']] = sales_stats.get(s['item'], 0) + s['qty']

        if not sales_stats:
            tk.Label(parent, text=f"{month} 無銷售紀錄", font=FONT_TITLE, bg="white").pack(pady=50)
            return

        labels = list(sales_stats.keys())
        sizes = list(sales_stats.values())
        
        fig = Figure(figsize=(7, 5), dpi=100)
        ax = fig.add_subplot(111)

        wedges, texts, autotexts = ax.pie(
                sizes,
                autopct='%1.1f%%',
                startangle=140,
                pctdistance=0.75,
                colors=plt.cm.Set3.colors,
                textprops=dict(color="black")
        )

        plt.setp(autotexts, size=10, weight="bold")
        ax.set_title(f"【{month}】各品項銷售佔比", fontsize=14)
        ax.legend(wedges, labels, title="品項列表", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
        self.embed_chart(parent, fig)

    # --- Chart 2: 折線圖 (進銷趨勢) ---
    def plot_trend_line(self, parent):
        month_keys = []
        curr = datetime.date.today()
        # 產生過去 6 個月的標籤
        for i in range(6):
            dt = curr - datetime.timedelta(days=30*i)
            month_keys.append(dt.strftime("%Y-%m"))
        month_keys.reverse()

        in_data = []
        out_data = []

        for m in month_keys:
            # 計算每月進貨量與銷貨量
            in_qty = sum([p['received_qty'] for p in self.data['po_db'] if p['delivery_date'].startswith(m)])
            in_data.append(in_qty)
            out_qty = sum([s['qty'] for s in self.data['sales_db'] if s['date'].startswith(m)])
            out_data.append(out_qty)

        fig = Figure(figsize=(6, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        ax.plot(month_keys, in_data, marker='o', label='進貨總量', color=COLORS['primary'])
        ax.plot(month_keys, out_data, marker='s', label='銷貨總量', color=COLORS['success'])
        
        ax.set_title("近半年進銷貨趨勢", fontsize=14)
        ax.set_xlabel("月份")
        ax.set_ylabel("數量")
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.6)

        self.embed_chart(parent, fig)

    # --- Chart 3: 單品分析 (互動式) ---
    def setup_individual_analysis(self, parent):
        self.clear_canvas(parent)
        ctrl = tk.Frame(parent, bg="white", pady=10)
        ctrl.pack(fill='x')
        tk.Label(ctrl, text="選擇商品:", font=FONT_BOLD, bg="white").pack(side='left', padx=10)
        
        items = list(self.data['stock_db'].keys())
        cb = ttk.Combobox(ctrl, values=items, font=FONT_MAIN)
        cb.pack(side='left')
        
        chart_frame = tk.Frame(parent, bg="white")
        chart_frame.pack(fill='both', expand=True)

        def draw_item_chart():
            item = cb.get()
            if not item: return
            self.clear_canvas(chart_frame)
            sales_history = [s for s in self.data['sales_db'] if s['item'] == item]
            sales_history.sort(key=lambda x: x['date'])
            
            if not sales_history:
                tk.Label(chart_frame, text="尚無銷售紀錄", font=FONT_TITLE, bg="white").pack(pady=50)
                return

            dates = [s['date'] for s in sales_history]
            qtys = [s['qty'] for s in sales_history]

            # 根據商品順序分配固定顏色
            if item in items: idx = items.index(item)
            else: idx = 0
            color_palette = plt.cm.Set3.colors 
            specific_color = color_palette[idx % len(color_palette)]

            fig = Figure(figsize=(6, 4), dpi=100)
            ax = fig.add_subplot(111)
            
            ax.bar(dates, qtys, color=specific_color, alpha=0.9, edgecolor='grey')
            ax.set_title(f"【{item}】 銷售紀錄", fontsize=14)
            ax.set_ylabel("銷售數量")
            fig.autofmt_xdate()
            self.embed_chart(chart_frame, fig)

        tk.Button(ctrl, text="分析", command=draw_item_chart, bg=COLORS["secondary"], fg="white", font=FONT_BOLD).pack(side='left', padx=10)

    # --- Chart 4: 財務長條圖 ---
    def plot_financial_bar(self, parent, month):
        total_cost = 0
        for a in self.data['ap_db']:
            if a['date'].startswith(month): total_cost += a['amt']
        
        total_rev = 0
        for s in self.data['sales_db']:
            if s['date'].startswith(month):
                rev = s.get('total', s.get('qty', 0) * s.get('price', 0))
                total_rev += rev
        
        gross_profit = total_rev - total_cost

        fig = Figure(figsize=(6, 5), dpi=100)
        ax = fig.add_subplot(111)
        cats = ['總收入', '總成本', '毛利']
        vals = [total_rev, total_cost, gross_profit]
        colors = [COLORS['success'], COLORS['danger'], COLORS['warning']]
        
        bars = ax.bar(cats, vals, color=colors)
        ax.set_title(f"{month} 財務概況", fontsize=14)
        ax.set_ylabel("金額 ($)")
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'${height:,.0f}',
                    ha='center', va='bottom')

        self.embed_chart(parent, fig)

    # --- Page 5: 庫存狀態列表 ---
    def init_list_page(self):
        cols = ("品項", "目前庫存", "狀態評估", "建議行動")
        self.tree_list = ttk.Treeview(self.page_list, columns=cols, show='headings')
        for c in cols: 
            self.tree_list.heading(c, text=c)
            self.tree_list.column(c, anchor='center')
        
        # 設定庫存過高或過低的顏色警示
        self.tree_list.tag_configure('low', background='#ffeaa7', foreground=COLORS["text"]) 
        self.tree_list.tag_configure('high', background='#55efc4', foreground=COLORS["text"])
        self.tree_list.tag_configure('even', background=COLORS["table_row_even"])
        self.tree_list.pack(fill='both', expand=True, padx=10, pady=10)

    def update_list_page(self):
        """ 檢查庫存水位並給出建議 """
        for row in self.tree_list.get_children(): self.tree_list.delete(row)
        idx = 0
        for item, qty in self.data['stock_db'].items():
            status, action, tag_special = "正常", "-", ""
            if qty < 5:
                status, action, tag_special = "⚠️ 庫存過低", "建議補貨", "low"
            elif qty > 100:
                status, action, tag_special = "📦 庫存過高", "建議促銷", "high"
            
            tag_row = 'even' if idx % 2 == 0 else 'odd'
            tags = (tag_row, tag_special) if tag_special else (tag_row,)
            self.tree_list.insert("", "end", values=(item, qty, status, action), tags=tags)
            idx += 1

# ================= 主程式進入點 =================
if __name__ == "__main__":
    root = tk.Tk()
    # 嘗試開啟 DPI 感知，讓高解析度螢幕顯示更清晰
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    app = AdvancedERPSystem(root)
    root.mainloop()
