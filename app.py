# ==============================================
# Verdulería Emilio - Flask App FINAL (Render Ready)
# ==============================================

import urllib.parse

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3, os, datetime
from fractions import Fraction
from urllib.parse import quote as urlencode
from werkzeug.utils import secure_filename

from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "emilio_local_secret")
app.debug = os.environ.get("FLASK_DEBUG", "0") == "1"

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")
ADMIN_PIN = os.environ.get("ADMIN_PIN", "1234")
EMILIO_WPP = os.environ.get("EMILIO_WPP", "5491126586256")

# carpeta de uploads dentro de static/img
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "img", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ------------------ Filtro Jinja ------------------
def decimal_a_fraccion(valor):
    try:
        fr = Fraction(valor).limit_denominator(4)
        return str(fr.numerator) if fr.denominator == 1 else f"{fr.numerator}/{fr.denominator}"
    except Exception:
        return str(valor)

app.jinja_env.filters["fraccion"] = decimal_a_fraccion

# ------------------ Base de datos ------------------
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, category TEXT, kind TEXT,
            price REAL, promo_qty REAL, promo_price REAL, image TEXT
        )""")
        con.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number INTEGER,
            created_at TEXT,
            customer_name TEXT,
            phone TEXT,
            pickup_time TEXT,
            note TEXT,
            payment TEXT,
            total REAL,
            place TEXT,
            delivery_address TEXT,
            status TEXT DEFAULT 'pendiente'
        )""")
        # Agregar columna status si no existe (para no romper db existentes)
        try:
            con.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'pendiente'")
        except:
            pass  # Columna ya existe
        con.execute("""
        CREATE TABLE IF NOT EXISTS order_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_name TEXT,
            qty REAL,
            unit TEXT,
            unit_price REAL,
            line_total REAL
        )""")
        con.execute("""
        CREATE TABLE IF NOT EXISTS reviews(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            rating INTEGER,
            comment TEXT,
            created_at TEXT
        )""")

init_db()

# ------------------ Funciones carrito ------------------
def get_cart():
    cart = session.get("cart", [])
    if not isinstance(cart, list):
        cart = []
    return cart

def save_cart(cart):
    session["cart"] = cart
    session.modified = True

def calcular_line_total(item):
    qty = float(item.get("qty", 1))
    price = float(item.get("price", 0))
    pq = item.get("promo_qty")
    pp = item.get("promo_price")
    if pq and pp and qty >= pq:
        promos = int(qty // pq)
        resto = qty % pq
        total = promos * pp + resto * price
    else:
        total = qty * price
    return round(total, 2)

def cart_total(cart):
    return round(sum(calcular_line_total(it) for it in cart), 2)

# ------------------ Página principal ------------------
@app.route("/")
def index():
    q = request.args.get("q", "").strip().lower()
    cat = request.args.get("cat", "").strip()

    # Acceso oculto al panel admin
    if q == "miverduleria":
        return redirect(url_for("login_admin"))

    with db() as con:
        rows = con.execute("SELECT * FROM products").fetchall()
        reseñas = con.execute("SELECT * FROM reviews ORDER BY id DESC LIMIT 5").fetchall()

    productos = [dict(r) for r in rows]
    if q:
        productos = [p for p in productos if q in p["name"].lower()]
    if cat:
        productos = [p for p in productos if p["category"] == cat]

    categories = sorted({p["category"] for p in productos})
    return render_template(
        "index.html",
        products=productos,
        categories=categories,
        q=q,
        cat=cat,
        cart=get_cart(),
        total=cart_total(get_cart()),
        ultimas_reseñas=[dict(r) for r in reseñas]
    )

# ------------------ API agregar al carrito ------------------
@app.post("/agregar_carrito")
def agregar_carrito():
    data = request.get_json(force=True)
    name = data.get("name")
    unit = data.get("unit")
    qty = float(data.get("qty", 1))
    unit_price = float(data.get("unit_price", 0))

    cart = get_cart()
    found = next((i for i in cart if i["name"] == name and i["unit"] == unit), None)
    if found:
        found["qty"] += qty
    else:
        cart.append({
            "name": name,
            "unit": unit,
            "price": unit_price,
            "qty": qty
        })
    save_cart(cart)
    return jsonify(ok=True, count=len(cart), total=cart_total(cart))

# ------------------ API borrar item del carrito ------------------
@app.post("/borrar_item")
def borrar_item():
    data = request.get_json(force=True)
    idx = int(data.get("index", -1))
    cart = get_cart()
    if 0 <= idx < len(cart):
        cart.pop(idx)
        save_cart(cart)
        return jsonify(ok=True, count=len(cart), total=cart_total(cart))
    return jsonify(ok=False)

# ------------------ Carrito ------------------
@app.route("/carrito")
def carrito():
    cart = get_cart()
    for item in cart:
        item["line_total"] = calcular_line_total(item)
        item["unit_price"] = item["price"]
    save_cart(cart)
    return render_template("carrito.html", cart=cart, total=cart_total(cart))

# ------------------ Pedido ------------------
@app.route("/pedido")
def pedido():
    cart = get_cart()
    if not cart:
        flash("Tu carrito está vacío.", "warning")
        return redirect(url_for("index"))
    for it in cart:
        it["line_total"] = calcular_line_total(it)
    return render_template("pedido.html", cart=cart, total=cart_total(cart))

# ------------------ Confirmar pedido ------------------
@app.post("/confirmar_pedido")
def confirmar_pedido():
    data = request.form

    # Datos del formulario
    name = data.get("nombre")
    phone = data.get("telefono")
    retiro = data.get("retiro")  # solo aplica si place == "retiro"
    nota = data.get("nota")

    cart = get_cart()
    if not cart:
        flash("Tu carrito está vacío.", "warning")
        return redirect(url_for("index"))

    # recalcular totales por seguridad
    for it in cart:
        it["line_total"] = calcular_line_total(it)
    total = cart_total(cart)

    # Lugar del pedido
    place = data.get("place")              # "retiro" o "delivery"
    delivery_address = data.get("delivery_address")
    pago = data.get("pago")  # compatibilidad vieja
    pago_final = data.get("pago_final") or pago or "Sin especificar"

    # Guardar en base
    with db() as con:
        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        # Número de pedido del día
        cur = con.execute(
            "SELECT COALESCE(MAX(number),0)+1 AS next FROM orders WHERE DATE(created_at)=?",
            (today,)
        )
        numero = cur.fetchone()["next"]

        con.execute("""
            INSERT INTO orders (
                number, created_at, customer_name, phone,
                pickup_time, note, payment, total, place, delivery_address, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            numero,
            fecha,
            name,
            phone,
            retiro if place == "retiro" else None,
            nota,
            pago_final,
            total,
            place,
            delivery_address if place == "delivery" else None,
            'pendiente'
        ))

        order_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        for it in cart:
            con.execute("""
                INSERT INTO order_items (
                    order_id, product_name, qty, unit, unit_price, line_total
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                it["name"],
                it["qty"],
                it["unit"],
                it["price"],
                calcular_line_total(it)
            ))

        con.commit()

    # ======== Mensaje de WhatsApp mejorado =========
    productos_txt = ""
    for it in cart:
        qty_fraccion = decimal_a_fraccion(it["qty"])
        productos_txt += (
            f"- {qty_fraccion} "
            f"{'Kg' if it['unit']=='kg' else 'u'} "
            f"de {it['name']} = ${it['line_total']:.2f}\n"
        )

    if place == "retiro":
        entrega_txt = f"🕐 Retiro en el local: {retiro}"
    else:
        entrega_txt = f"🚚 Delivery a: {delivery_address}"

    texto = (
        f"🧺 *Nuevo pedido*\n\n"
        f"✅ *Pedido #{numero}*\n\n"
        f"👤 Cliente: {name}\n"
        f"📞 Teléfono: {phone}\n"
        f"{entrega_txt}\n"
        f"💳 Forma de pago: {pago_final}\n\n"
        f"📦 *Detalle del pedido:*\n{productos_txt}\n"
        f"💰 *Total:* ${total:.2f}\n"
        f"📝 Nota del cliente: {nota if nota else 'Sin notas'}"
    )

    texto_codificado = urllib.parse.quote(texto)
    wpp_url = f"https://wa.me/{EMILIO_WPP}?text={texto_codificado}"

    # Vaciar carrito después de armar todo
    session.pop("cart", None)
    session.modified = True

    # Mostrar resumen en HTML (pedido ya confirmado en la base)
    return render_template(
        "pedido_confirmado.html",
        order_id=order_id,
        numero_pedido=numero,
        nombre=name,
        telefono=phone,
        retiro=retiro if place == "retiro" else None,
        delivery_address=delivery_address if place == "delivery" else None,
        place=place,
        pago=pago_final,
        nota=nota,
        total=total,
        productos=cart,
        wpp_url=wpp_url,
        fecha=datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    )

# ------------------ Marcar pedido como enviado ------------------
@app.post("/marcar_enviado")
def marcar_enviado():
    try:
        data = request.get_json()
        order_id = data.get("order_id")
        
        if not order_id:
            return jsonify({"success": False, "error": "order_id no proporcionado"}), 400
        
        with db() as con:
            con.execute(
                "UPDATE orders SET status = 'enviado' WHERE id = ?",
                (order_id,)
            )
            con.commit()
        
        return jsonify({"success": True, "message": "Pedido marcado como enviado"})
    except Exception as e:
        print("Error en /marcar_enviado:", e)
        return jsonify({"success": False, "error": str(e)}), 500

# ------------------ Contacto / reseñas ------------------
@app.route("/contacto", methods=["GET", "POST"])
def contacto():
    if request.method == "POST":
        try:
            nombre = request.form.get("nombre", "").strip()
            comentario = request.form.get("comentario", "").strip()
            rating = request.form.get("rating", "").strip()
            if not nombre or not comentario or not rating.isdigit():
                flash("Por favor completá todos los campos y elegí una puntuación.", "danger")
                return redirect(url_for("contacto"))
            rating = int(rating)
            fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            with db() as con:
                con.execute(
                    "INSERT INTO reviews (name, rating, comment, created_at) VALUES (?, ?, ?, ?)",
                    (nombre, rating, comentario, fecha)
                )
                con.commit()
            flash("¡Gracias por tu reseña!", "success")
            return redirect(url_for("contacto"))
        except Exception as e:
            print("Error en /contacto:", e)
            flash("Ocurrió un error al enviar tu reseña.", "danger")
            return redirect(url_for("contacto"))
    return render_template("contacto.html", cart=get_cart(), total=cart_total(get_cart()))

# ---------------------- Admin: login ----------------------
@app.route("/login_admin", methods=["GET", "POST"])
def login_admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PIN:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        else:
            return render_template("login_admin.html", error="PIN incorrecto")
    return render_template("login_admin.html")

# ---------------------- Admin: panel principal ----------------------
@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return redirect(url_for("login_admin"))

    with db() as con:
        productos = [dict(r) for r in con.execute("SELECT * FROM products ORDER BY category, name")]
        pedidos = [dict(r) for r in con.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 20")]
        reseñas = [dict(r) for r in con.execute("SELECT * FROM reviews ORDER BY id DESC LIMIT 20")]

    return render_template("admin.html", products=productos, orders=pedidos, reseñas=reseñas, mode="list")

# ---------------------- Admin: cerrar sesión ----------------------
@app.route("/logout_admin")
def logout_admin():
    session.pop("is_admin", None)
    flash("Sesión de administrador cerrada.", "info")
    return redirect(url_for("index"))

# ---------------------- Admin: nuevo producto ----------------------
@app.route("/admin_new", methods=["GET", "POST"])
def admin_new():
    if not session.get("is_admin"):
        return redirect(url_for("login_admin"))

    if request.method == "POST":
        nombre = request.form.get("name")
        categoria = request.form.get("category")
        tipo = request.form.get("kind")
        precio = float(request.form.get("price", 0))
        promo_qty = request.form.get("promo_qty")
        promo_price = request.form.get("promo_price")
        # campo de texto (ruta dentro de static/img) opcional
        image_field = request.form.get("image", "").strip()

        # archivo subido desde dispositivo (gallery / file picker)
        image_file = request.files.get("image_file")
        image_path = image_field or ""
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            # hacerlo único
            filename = f"{int(datetime.datetime.now().timestamp())}_{filename}"
            dest = os.path.join(UPLOAD_FOLDER, filename)
            image_file.save(dest)
            # ruta relativa para usar en templates: static/img/... -> almacenamos 'img/uploads/...'
            image_path = f"img/uploads/{filename}"

        with db() as con:
            con.execute("""
                INSERT INTO products (name, category, kind, price, promo_qty, promo_price, image)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (nombre, categoria, tipo, precio, promo_qty, promo_price, image_path))
            con.commit()

        flash("Producto agregado correctamente.", "success")
        return redirect(url_for("admin"))

    return render_template("admin_form.html", product=None)

# ---------------------- Admin: editar producto ----------------------
@app.route("/admin_edit/<int:pid>", methods=["GET", "POST"])
def admin_edit(pid):
    if not session.get("is_admin"):
        return redirect(url_for("login_admin"))

    with db() as con:
        producto = con.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()

    if not producto:
        flash("Producto no encontrado.", "danger")
        return redirect(url_for("admin"))

    if request.method == "POST":
        nombre = request.form.get("name")
        categoria = request.form.get("category")
        tipo = request.form.get("kind")
        precio = float(request.form.get("price", 0))
        promo_qty = request.form.get("promo_qty")
        promo_price = request.form.get("promo_price")
        image_field = request.form.get("image", "").strip()

        image_file = request.files.get("image_file")
        image_path = image_field or producto["image"] or ""
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            filename = f"{int(datetime.datetime.now().timestamp())}_{filename}"
            dest = os.path.join(UPLOAD_FOLDER, filename)
            image_file.save(dest)
            image_path = f"img/uploads/{filename}"

        with db() as con:
            con.execute("""
                UPDATE products
                SET name=?, category=?, kind=?, price=?, promo_qty=?, promo_price=?, image=?
                WHERE id=?
            """, (nombre, categoria, tipo, precio, promo_qty, promo_price, image_path, pid))
            con.commit()

        flash("Producto actualizado correctamente.", "success")
        return redirect(url_for("admin"))

    return render_template("admin_form.html", product=producto)

# ---------------------- Admin: borrar producto ----------------------
@app.post("/admin_delete/<int:pid>")
def admin_delete(pid):
    if not session.get("is_admin"):
        return redirect(url_for("login_admin"))

    with db() as con:
        con.execute("DELETE FROM products WHERE id = ?", (pid,))
        con.commit()

    flash("Producto eliminado correctamente.", "info")
    return redirect(url_for("admin"))

# ------------------ Admin: eliminar pedido individual ------------------
@app.post("/eliminar_pedido/<int:order_id>")
def eliminar_pedido(order_id):
    if not session.get("is_admin"):
        return redirect(url_for("login_admin"))

    with db() as con:
        con.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        con.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        con.commit()

    flash("🗑️ Pedido eliminado correctamente.", "info")
    return redirect(url_for("admin"))

# ------------------ Admin: eliminar todos los pedidos ------------------
@app.post("/eliminar_todos_pedidos")
def eliminar_todos_pedidos():
    if not session.get("is_admin"):
        return redirect(url_for("login_admin"))

    with db() as con:
        con.execute("DELETE FROM order_items")
        con.execute("DELETE FROM orders")
        con.commit()

    flash("🧹 Todos los pedidos fueron eliminados correctamente.", "warning")
    return redirect(url_for("admin"))

# ---------------------- Admin: eliminar reseña ----------------------
@app.post("/eliminar_resena/<int:review_id>")
def eliminar_resena(review_id):
    if not session.get("is_admin"):
        return redirect(url_for("login_admin"))

    with db() as con:
        con.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        con.commit()

    flash("Reseña eliminada.", "info")
    return redirect(url_for("admin"))

# ---------------------- INICIAR SERVIDOR ----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
