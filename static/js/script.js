// 🧠 Copilot instruction:
// I’m working on a Flask-based store web app (Verdulería Emilio).
// The cart buttons in catalog (index.html) stopped working — they should add items to cart via fetch('/agregar_carrito').
// The code already includes .add-btn for green buttons and .promo-btn for yellow promo buttons.
// Review script.js, app.py, and HTML templates to fix the JavaScript so all buttons add correctly to the cart.
// Keep all existing structure, variable names, and Flask endpoints exactly as they are.
// DO NOT delete or rename anything, only repair and reconnect event handlers or fetch calls if needed.
// If a function like syncMiniCart, addToCart, or agregar_carrito exists, reuse it.
// After fixing, ensure both “Agregar al carrito” and “Promo” buttons trigger correctly and the mini-cart updates.
// Write your improved code suggestion below, inside script.js only.


(function(){
  const miniCount = document.getElementById('mini-count');
  const miniCart  = document.getElementById('mini-cart');
  const miniTotal = document.getElementById('mini-total');

  // pinta minicart (cuando esté en el DOM)
  function syncMini(count, total){
    if (miniCount) miniCount.textContent = count || 0;
    if (miniTotal) miniTotal.textContent = `$ ${Number(total||0).toFixed(2)}`;
  }
  syncMini(window.CART_COUNT || 0, window.CART_TOTAL || 0);

  // seleccionar peso para productos por Kg
  document.querySelectorAll('.qty-btn').forEach(btn=>{
    btn.addEventListener('click', e=>{
      const card = e.target.closest('.card');
      // toggle visual
      card.querySelectorAll('.qty-btn').forEach(b=>b.classList.remove('active'));
      e.target.classList.add('active');
      // almacena la cantidad elegida
      card.querySelector('.picked-qty').value = e.target.dataset.qty;
    });
  });

  // promo preconfigurada y agregar promo al carrito
  document.querySelectorAll('.promo-btn').forEach(btn=>{
    btn.addEventListener('click', async e=>{
      e.preventDefault(); // <-- evita submit de formulario
      const card = e.target.closest('.card');
      card.querySelectorAll('.qty-btn').forEach(b=>b.classList.remove('active'));
      // guardo la promo como "cantidad elegida" y cambio precio unitario temporal
      const qty = parseFloat(btn.dataset.qty);
      const pricePromo = parseFloat(btn.dataset.price);
      card.querySelector('.picked-qty') && (card.querySelector('.picked-qty').value = qty);
      // truco: sobreescribo data-unitprice para que el total = promo
      const add = card.querySelector('.add-btn');
      add.dataset.unitprice = (pricePromo / qty).toString();

      // Enviar promo al carrito
      const name = card.querySelector('.card-title').textContent.trim();
      const unit = add.dataset.unit;
      const unit_price = pricePromo / qty;
      const resp = await fetch('/agregar_carrito', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, unit, qty, unit_price })
      }).then(r => r.json());

      if (resp.ok) {
        syncMini(resp.count, resp.total);
        btn.innerText = 'Promo agregada ✓';
        btn.classList.remove('btn-warning');
        btn.classList.add('btn-secondary');
        setTimeout(() => {
          btn.innerText = `Promo: ${qty} ${unit === 'kg' ? 'Kg' : 'u'} x $${pricePromo}`;
          btn.classList.remove('btn-secondary');
          btn.classList.add('btn-warning');
        }, 1200);
      }
    });
  });

  // agregar al carrito
  document.querySelectorAll('.add-btn').forEach(btn=>{
    btn.addEventListener('click', async e=>{
      e.preventDefault(); // <-- evita submit de formulario
      const card = e.target.closest('.card');
      const name = e.target.dataset.name;
      const unit = e.target.dataset.unit;
      let qty = 1;
      if (unit === 'kg'){
        qty = parseFloat(card.querySelector('.picked-qty').value || '0');
        if (!qty){ alert('Elegí 1/4, 1/2 o 1 Kg (o Promo)'); return; }
      } else {
        qty = parseInt(card.querySelector('.picked-units').value || '1', 10);
        if (qty < 1){ alert('Cantidad inválida'); return; }
      }
      const unit_price = parseFloat(e.target.dataset.unitprice);

      const resp = await fetch('/agregar_carrito', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({name, unit, qty, unit_price})
      }).then(r=>r.json());

      if (resp.ok){
        syncMini(resp.count, resp.total);
        // feedback visual
        e.target.innerText = 'Agregado ✓';
        e.target.classList.remove('btn-success');
        e.target.classList.add('btn-secondary');
        setTimeout(()=>{
          e.target.innerText = 'Agregar al carrito';
          e.target.classList.remove('btn-secondary');
          e.target.classList.add('btn-success');
        }, 800);
      }
    });
  });

  // borrar en carrito
  document.querySelectorAll('.del-item').forEach(btn=>{
    btn.addEventListener('click', async e=>{
      const idx = parseInt(e.target.dataset.index,10);
      const resp = await fetch('/borrar_item', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({index: idx})
      }).then(r=>r.json());
      if (resp.ok) location.reload();
    });
  });
})();
// El JS ya agrega promos por unidad y por kilo correctamente

// --- Acceso oculto al panel admin ---
// Redirige si el usuario escribe "emilio2025" en cualquier parte
document.addEventListener('keydown', (function() {
  let buffer = '';
  let timer;
  return function(e) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => { buffer = ''; }, 2000);
    if (e.key.length === 1) buffer += e.key;
    if (buffer.toLowerCase().includes('emilio2025')) {
      buffer = '';
      window.location.href = '/login_admin';
    }
  };
})());

// Triple toque en el logo para pantallas táctiles
(function() {
  const logo = document.querySelector('.navbar-brand img');
  if (!logo) return;
  let tapCount = 0;
  let tapTimer = null;
  logo.addEventListener('touchend', function() {
    tapCount++;
    if (tapCount === 1) {
      tapTimer = setTimeout(() => { tapCount = 0; }, 3000);
    }
    if (tapCount === 3) {
      tapCount = 0;
      clearTimeout(tapTimer);
      window.location.href = '/login_admin';
    }
  });
})();
