# 🚀 INSTRUCCIONES DE DEPLOY EN RENDER

## ✅ Paso 1: Preparar el repositorio (LOCAL)

### 1.1 Agregar cambios a Git
```powershell
cd "c:\Users\User\Desktop\Proyectos PGestion\mi verdueria para ofrecer"
git add .
git commit -m "Preparar para deploy en Render"
git push origin main
```

---

## ✅ Paso 2: Crear un Web Service en Render

### 2.1 Ir a Render.com
1. Ve a https://render.com
2. Crea una cuenta o inicia sesión
3. En el dashboard, haz clic en "New +"
4. Selecciona "Web Service"

### 2.2 Conectar tu repositorio
1. Selecciona "GitHub" como proveedor de repositorio
2. Autoriza a Render a acceder a tu GitHub
3. Selecciona tu repositorio `verduleria-emilio`
4. Haz clic en "Connect"

### 2.3 Configurar el Web Service

**Nombre del servicio:**
```
mi-verduleria
```

**Región:**
```
Frankfurt (eu-central-1)  [o la más cercana a ti]
```

**Rama:**
```
main
```

**Comando de construcción (Build Command):**
```
bash build.sh
```

**Comando de inicio (Start Command):**
```
gunicorn app:app
```

**Plan:**
```
Free [o superior según necesites]
```

### 2.4 Agregar Variables de Entorno

En la sección "Environment" agrega estas variables:

| Clave | Valor |
|-------|-------|
| `SECRET_KEY` | `tu_clave_segura_aleatoria_aqui` * |
| `ADMIN_PIN` | `tu_pin_admin` |
| `EMILIO_WPP` | `5491126586256` |
| `FLASK_ENV` | `production` |
| `FLASK_DEBUG` | `0` |
| `PORT` | `10000` |

**\* Para SECRET_KEY, genera algo como:**
```
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2.5 Crear el servicio
Haz clic en "Create Web Service" y espera a que termine el deployment.

---

## ✅ Paso 3: Verificar el deployment

Una vez que Render termine:

1. Tu app estará disponible en una URL como:
   ```
   https://mi-verduleria.onrender.com
   ```

2. Verifica que funcione:
   - Accede a https://mi-verduleria.onrender.com
   - Prueba agregar un producto
   - Prueba hacer un pedido
   - Prueba el login admin (miverduleria en búsqueda)

3. **Consulta los logs:**
   - Ve al dashboard de tu servicio en Render
   - Haz clic en "Logs"
   - Si hay errores, aparecerán ahí

---

## ✅ Paso 4: Configurar dominio personalizado (OPCIONAL)

Si quieres usar tu propio dominio (ej: www.midulceria.com):

1. En Render, ve a "Settings" de tu servicio
2. En "Custom Domain", agrega tu dominio
3. En tu proveedor de dominio, apunta los DNS a Render
4. Render te dará las instrucciones exactas

---

## ⚠️ Notas importantes

### Base de datos
- Tu archivo `database.db` se crea automáticamente
- **IMPORTANTE:** En cada re-deploy, la BD se reinicia a cero
- Para producción, considera usar PostgreSQL (Render lo ofrece gratis con límites)

### Archivos estáticos
- `static/css`, `static/js` y `static/img` se sirven correctamente
- Los uploads se guardan en `static/img/uploads/`

### Rendimiento
- El plan Free de Render duerme después de 15 min sin actividad
- Tarda ~1 min en despertar (cold start)
- Considera plan Starter para mejor performance

### Actualizaciones futuras
- Cada `git push` a main redeploy automáticamente
- Los redeploy reinician desde cero

---

## 🐛 Troubleshooting

**Si ves "Build failed":**
- Verifica que el `build.sh` tenga permisos correctos
- Revisa los logs en Render
- Asegúrate que `patch.py` no falla

**Si la base de datos está vacía:**
- Es normal en el primer deploy
- Ve a `/admin` (miverduleria en búsqueda) y agrega productos manualmente
- O modifica `patch.py` para insertar datos de prueba

**Si el sitio es lento:**
- Es posible que esté durmiendo (plan Free)
- Accede nuevamente
- Considera upgrade a plan Starter

---

## ✨ Comandos útiles en Render

**Ver logs en tiempo real:**
- Dashboard → Logs

**Redeploy manualmente:**
- Dashboard → Manual Deploy → Deploy latest commit

**Ver variables de entorno:**
- Dashboard → Environment

---

¡Listo! Tu verdulería debería estar online en Render. 🎉
