from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3, os, datetime
from fractions import Fraction  # 👈 agregado acá

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "emilio_local_secret")

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")
ADMIN_PIN = os.environ.get("ADMIN_PIN", "1234")  # PIN simple para el admin


# ✅ Filtro para convertir decimales a fracciones
def decimal_a_fraccion(valor):
    try:
        fraccion = Fraction(valor).limit_denominator(4)  # hasta cuartos
        if fraccion.denominator == 1:
            return str(fraccion.numerator)  # ejemplo: 1
        else:
            return f"{fraccion.numerator}/{fraccion.denominator}"
    except:
        return str(valor)

# Registrar el filtro en Jinja2
app.jinja_env.filters['fraccion'] = decimal_a_fraccion

# ---------------------- DB helpers ----------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        # --- MIGRACIÓN orders.number UNIQUE a índice compuesto ---
        try:
            # Detecta si la tabla orders tiene UNIQUE en number
            table_sql = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='orders'").fetchone()
            needs_migration = table_sql and "UNIQUE" in table_sql["sql"]
            if needs_migration:
                # Renombra la tabla vieja
                con.execute("ALTER TABLE orders RENAME TO orders_old")
                # Crea la nueva tabla sin UNIQUE en number
                con.execute("""
                CREATE TABLE orders(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    number INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    customer_name TEXT,
                    phone TEXT,
                    pickup_time TEXT,
                    note TEXT,
                    payment TEXT,
                    total REAL NOT NULL
                )
                """)
                # Copia los datos
                con.execute("""
                INSERT INTO orders (id, number, created_at, customer_name, phone, pickup_time, note, payment, total)
                SELECT id, number, created_at, customer_name, phone, pickup_time, note, payment, total FROM orders_old
                """)
                # Borra la tabla vieja
                con.execute("DROP TABLE orders_old")
        except Exception as e:
            print("Migración de orders.number UNIQUE falló o no es necesaria:", e)

        # Crea el índice único compuesto por number y DATE(created_at)
        try:
            con.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_number_date
            ON orders(number, DATE(created_at))
            """)
        except Exception as e:
            print("No se pudo crear el índice compuesto:", e)

        con.execute("""
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            kind TEXT NOT NULL,
            price REAL NOT NULL,
            promo_qty REAL,
            promo_price REAL,
            image TEXT
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS order_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            qty REAL NOT NULL,
            unit TEXT NOT NULL,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS reviews(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            rating INTEGER,
            comment TEXT,
            created_at TEXT
        )
        """)

        # seed si no hay productos
        cur = con.execute("SELECT COUNT(*) AS c FROM products")
        if cur.fetchone()["c"] == 0:
            con.executemany("""
            INSERT INTO products (name,category,kind,price,promo_qty,promo_price,image)
            VALUES (?,?,?,?,?,?,?)
            """, [
                ("Manzanas", "Frutas", "kg",   800, 2.0, 1400, "static/img/placeholder.jpg"),
                ("Papas",     "Verduras", "kg", 500, 3.0, 1500, "static/img/placeholder.jpg"),
                ("Morrones",  "Verduras", "kg",1200, 3.0, 3200, "static/img/placeholder.jpg"),
                ("Carbón bolsa", "Otros", "unit", 1000, None, None, "static/img/placeholder.jpg"),
                ("Maple huevos", "Otros", "unit", 1500, None, None, "static/img/placeholder.jpg"),
            ])

init_db()

# ---------------------- util carrito ----------------------
def get_cart():
    cart = session.get("cart")
    if cart is None or not isinstance(cart, list):
        session["cart"] = []
        session.modified = True
        return []
    return session["cart"]

def save_cart(cart):
    # Convierte todos los items a dicts con tipos nativos
    safe_cart = []
    for item in cart:
        safe_cart.append({
            "name": str(item["name"]),
            "unit": str(item["unit"]),
            "qty": float(item["qty"]),
            "unit_price": float(item["unit_price"]),
            "line_total": float(item["line_total"])
        })
    session["cart"] = safe_cart
    session.modified = True

def cart_total(cart):
    return round(sum(item["line_total"] for item in cart), 2)

# Calcula el total de cada línea con promociones (por kg o por unidad)
def calcular_line_total(item):
    qty = float(item["qty"])
    # Cambia 'precio' por 'price' (de la base de datos) o 'unit_price' (del carrito)
    price = float(item.get("price", item.get("unit_price", 0)))
    promo_qty = item.get("promo_qty")
    promo_price = item.get("promo_price")

    if promo_qty and promo_price and qty >= promo_qty:
        promos = int(qty // promo_qty)
        resto = qty % promo_qty
        total = promos * promo_price + resto * price
    else:
        total = qty * price

    return round(total, 2)


# Calcula el total del carrito completo
def cart_total(cart):
    return round(sum(calcular_line_total(it) for it in cart), 2)


# ---------------------- rutas públicas ----------------------




@app.route("/")
def index():
    q = request.args.get("q", "").strip().lower()
    cat = request.args.get("cat", "").strip()
    with db() as con:
        rows = con.execute("SELECT * FROM products").fetchall()
        ultimas_reseñas = [dict(r) for r in con.execute(
            "SELECT * FROM reviews ORDER BY id DESC LIMIT 5"
        )]
    products = [dict(r) for r in rows]

    if q:
        products = [p for p in products if q in p["name"].lower()]
    if cat:
        products = [p for p in products if p["category"] == cat]

    # categorías para el sidebar
    categories = sorted({p["category"] for p in products} | 
                        {p["category"] for p in [dict(r) for r in rows]})

    return render_template("index.html",
                           products=products,
                           categories=categories,
                           q=q, cat=cat,
                           cart=get_cart(), total=cart_total(get_cart()),
                           ultimas_reseñas=ultimas_reseñas)

@app.post("/agregar_carrito")
def agregar_carrito():
    data = request.get_json(force=True)
    # Validación y conversión segura de datos
    try:
        name = str(data.get("name", "")).strip()
        unit = str(data.get("unit", "kg")).strip()
        qty_raw = data.get("qty", 1)
        unit_price_raw = data.get("unit_price", 0)
        try:
            qty = float(qty_raw)
        except (TypeError, ValueError):
            qty = 1.0
        try:
            unit_price = float(unit_price_raw)
        except (TypeError, ValueError):
            unit_price = 0.0
        line_total = round(qty * unit_price, 2)
        # Detecta si es promo (si viene data.price y qty coincide con promo_qty)
        is_promo = False
        if "price" in data and "qty" in data:
            # Si el precio unitario es diferente al precio normal, es promo
            try:
                promo_price = float(data.get("price", 0))
                if promo_price and abs(promo_price - line_total) < 0.01:
                    is_promo = True
            except Exception:
                pass
        # Alternativamente, si el JS envía un flag promo, úsalo
        if data.get("promo") is True:
            is_promo = True
    except Exception as ex:
        return jsonify({"ok": False, "error": "Datos inválidos", "detail": str(ex)}), 400

    # Guarda en session["cart"]
    cart = session.get("cart")
    if not isinstance(cart, list):
        cart = []
    cart.append({
        "name": name,
        "unit": unit,
        "qty": qty,
        "unit_price": unit_price,
        "line_total": line_total,
        "promo": is_promo
    })
    session["cart"] = cart
    session.modified = True

    # Calcula el total del carrito
    total = round(sum(item.get("line_total", 0) for item in cart), 2)
    return jsonify({"ok": True, "count": len(cart), "total": total})

@app.post("/borrar_item")
def borrar_item():
    idx = int(request.get_json(force=True)["index"])
    cart = get_cart()
    if 0 <= idx < len(cart):
        cart.pop(idx)
        save_cart(cart)
    return jsonify({"ok": True, "count": len(cart), "total": cart_total(cart)})

@app.route("/carrito")
def carrito():
    return render_template("carrito.html",
                           cart=get_cart(),
                           total=cart_total(get_cart()))

@app.route("/pedido")
def pedido():
    # Form de datos del cliente
    return render_template("pedido.html",
                           cart=get_cart(), total=cart_total(get_cart()))

@app.post("/confirmar_pedido")
def confirmar_pedido():
    payload = request.form
    name   = payload.get("nombre", "").strip()
    phone  = payload.get("telefono", "").strip()
    pickup = payload.get("retiro", "").strip() or "Sin horario"
    note   = payload.get("nota", "").strip() or "Ninguna"
    pay    = payload.get("pago", "Efectivo")

    cart = get_cart()
    total = cart_total(cart)

    with db() as con:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        cur = con.execute(
            "SELECT COALESCE(MAX(number),0)+1 AS next FROM orders WHERE DATE(created_at)=?",
            (today_str,)
        )
        next_number = cur.fetchone()["next"]
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # 🔹 Inserta el pedido en 'orders'
        con.execute("""
            INSERT INTO orders (number, created_at, customer_name, phone, pickup_time, note, payment, total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (next_number, now, name, phone, pickup, note, pay, total))

        order_id = con.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        # 🔹 Inserta los ítems del carrito
        for it in cart:
            con.execute("""
                INSERT INTO order_items (order_id, product_name, qty, unit, unit_price, line_total)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (order_id, it["name"], it["qty"], it["unit"], it["unit_price"], it["line_total"]))

        con.commit()

    # 🔹 Limpia el carrito
    session.pop("cart", None)
    session.modified = True

    numero_emilio = os.environ.get("EMILIO_WPP", "5491167890400")
    texto = (
        f"Pedido #{next_number}\n"
        f"Cliente: {name} ({phone})\n"
        f"Retiro: {pickup}\n"
        f"Pago: {pay}\n"
        f"Nota: {note}\n"
        "---\n"
        "🛒 Productos:\n"
    )
    for it in cart:
        cantidad = it["qty"]
        unidad = "Kg" if it["unit"] == "kg" else "u"
        texto += f"• {cantidad} {unidad} de {it['name']} = ${it['line_total']:.2f}\n"
    texto += "---\n"
    texto += f"💰 Total: ${total:.2f}\n"

    from urllib.parse import quote as urlencode
    wpp_url = f"https://wa.me/{numero_emilio}?text={urlencode(texto)}"

    return render_template(
        "pedido_confirmado.html",
        numero_pedido=next_number,
        fecha=now,
        nombre=name,
        telefono=phone,
        retiro=pickup,
        pago=pay,
        nota=note,
        productos=cart,
        total=total,
        wpp_url=wpp_url
    )



@app.route("/contacto")
def contacto():
    return render_template("contacto.html")

@app.route("/enviar_resena", methods=["POST"])
def enviar_resena():
    name = request.form.get("nombre", "").strip()
    rating = int(request.form.get("rating", "0"))
    comment = request.form.get("comentario", "").strip()
    if rating < 1 or rating > 5:
        flash("Por favor, seleccioná una puntuación de estrellas.", "danger")
        return redirect(url_for("contacto"))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with db() as con:
        con.execute(
            "INSERT INTO reviews (name, rating, comment, created_at) VALUES (?, ?, ?, ?)",
            (name, rating, comment, now)
        )
        con.commit()
    flash("Gracias por tu reseña", "success")
    return redirect(url_for("contacto"))

# ---------------------- ADMIN (PIN simple) ----------------------
@app.route("/admin", methods=["GET","POST"])
def admin():
    # --- Solo permite acceso si está logueado como admin ---
    if not session.get("is_admin"):
        return redirect(url_for("login_admin"))

    # login por PIN guardado en sesión
    if request.method == "POST" and request.form.get("pin") == ADMIN_PIN:
        session["is_admin"] = True
    if not session.get("is_admin"):
        return render_template("admin.html", mode="login")

    # listado de productos
    with db() as con:
        products = [dict(r) for r in con.execute("SELECT * FROM products ORDER BY category, name")]
        # Corrige el filtro de pedidos del día para TEXT (created_at)
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        orders = [dict(r) for r in con.execute(
            "SELECT * FROM orders WHERE created_at LIKE ? ORDER BY id DESC",
            (f"{today}%",)
        )]
        # Carga las últimas 50 reseñas
        reseñas = [dict(r) for r in con.execute(
            "SELECT * FROM reviews ORDER BY id DESC LIMIT 50"
        )]

    return render_template("admin.html", mode="list", products=products, orders=orders, reseñas=reseñas)

@app.post("/eliminar_resena/<int:review_id>")
def eliminar_resena(review_id):
    with db() as con:
        con.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        con.commit()
    flash("Reseña eliminada correctamente.", "success")
    return redirect(url_for("admin"))


@app.get("/admin/salir")
def admin_salir():
    session.pop("is_admin", None)
    return redirect(url_for("admin"))

@app.route("/admin/producto/nuevo", methods=["GET","POST"])
def admin_new():
    if not session.get("is_admin"): return redirect(url_for("admin"))
    if request.method == "POST":
        f = request.form
        with db() as con:
            con.execute("""
            INSERT INTO products(name,category,kind,price,promo_qty,promo_price,image)
            VALUES (?,?,?,?,?,?,?)
            """,(f["name"], f["category"], f["kind"], float(f["price"] or 0),
                 float(f["promo_qty"] or 0) if f["promo_qty"] else None,
                 float(f["promo_price"] or 0) if f["promo_price"] else None,
                 f["image"] or "static/img/placeholder.jpg"))
        return redirect(url_for("admin"))
    return render_template("admin_form.html", product=None)

@app.route("/admin/producto/<int:pid>/editar", methods=["GET","POST"])
def admin_edit(pid):
    if not session.get("is_admin"): return redirect(url_for("admin"))
    with db() as con:
        p = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p: return redirect(url_for("admin"))
    if request.method == "POST":
        f = request.form
        with db() as con:
            con.execute("""
            UPDATE products
               SET name=?, category=?, kind=?, price=?, promo_qty=?, promo_price=?, image=?
             WHERE id=?
            """,(f["name"], f["category"], f["kind"], float(f["price"] or 0),
                 float(f["promo_qty"] or 0) if f["promo_qty"] else None,
                 float(f["promo_price"] or 0) if f["promo_price"] else None,
                 f["image"] or "static/img/placeholder.jpg",
                 pid))
        return redirect(url_for("admin"))
    return render_template("admin_form.html", product=dict(p))

@app.post("/admin/producto/<int:pid>/borrar")
def admin_delete(pid):
    if not session.get("is_admin"): return redirect(url_for("admin"))
    with db() as con:
        con.execute("DELETE FROM products WHERE id=?", (pid,))
    return redirect(url_for("admin"))

@app.route("/admin/limpiar_pedidos", methods=["POST"])
def admin_limpiar_pedidos():
    # 3. Borra todos los pedidos anteriores al día actual y muestra mensaje flash
    if not session.get("is_admin"): return redirect(url_for("admin"))
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    with db() as con:
        con.execute("DELETE FROM orders WHERE DATE(created_at) < DATE('now')")
        # Borra los items asociados a los pedidos eliminados
        con.execute("""
            DELETE FROM order_items
            WHERE order_id NOT IN (SELECT id FROM orders)
        """)
    flash("Pedidos anteriores al día actual eliminados.", "success")
    return redirect(url_for("admin"))

@app.route("/eliminar_pedido/<int:order_id>", methods=["POST"])
def eliminar_pedido(order_id):
    if not session.get("is_admin"): return redirect(url_for("admin"))
    with db() as con:
        con.execute("DELETE FROM order_items WHERE order_id=?", (order_id,))
        con.execute("DELETE FROM orders WHERE id=?", (order_id,))
    flash("Pedido eliminado.", "success")
    return redirect(url_for("admin"))

@app.route("/eliminar_todos_pedidos", methods=["POST"])
def eliminar_todos_pedidos():
    if not session.get("is_admin"):
        return redirect(url_for("admin"))

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    with db() as con:
        # Elimina los ítems de los pedidos del día
        con.execute("""
            DELETE FROM order_items 
            WHERE order_id IN (
                SELECT id FROM orders WHERE DATE(created_at) = DATE('now')
            )
        """)
        # Elimina los pedidos del día
        con.execute("DELETE FROM orders WHERE DATE(created_at) = DATE('now')")
        con.commit()

    flash("Pedidos del día eliminados.", "success")
    return redirect(url_for("admin"))

# --- Ruta oculta para login admin ---
@app.route("/login_admin", methods=["GET", "POST"])
def login_admin():
    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        # Cambia la contraseña aquí si lo deseas
        if password == "emilio2025":
            session["is_admin"] = True
            return redirect(url_for("admin"))
        else:
            error = "Contraseña incorrecta"
    return render_template("login_admin.html", error=error)

# ------------------- main -------------------
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)







