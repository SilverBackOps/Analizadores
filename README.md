# Analizador de Motivos de Compra (CLI)

Aplicación CLI sencilla (línea de comandos) en Python que analiza una página de producto y estima **los motivos probables por los que un consumidor decide comprarlo**.

Utiliza texto del título, descripción y reseñas (si las hay) para identificar patrones asociados a drivers de compra: precio, calidad, envío, marca/confianza, características, usabilidad, estética, compatibilidad, necesidad y recomendación social.

---

## ✅ Características
- **Interfaz interactiva** desde la terminal
- Análisis heurístico de texto del producto
- Extracción automática de:
  - Título del producto
  - Precio detectable
  - Descripción ampliada
  - Reseñas (si la web las expone en HTML)
- Cálculo de “drivers” de compra mediante palabras clave
- Visualización con **barras de proporción**
- Exportación opcional a **JSON**
- Manejo de errores de red y respuestas 403
- Rotación de User-Agent y cabeceras típicas de navegador
- Soporte opcional para:
  - Cookies (si hace falta autenticación)
  - Proxy HTTP/HTTPS

---

## 📦 Requisitos

### Dependencias del sistema
Python 3.8+  
Linux (tested in Debian/Kali/Ubuntu)

### Dependencias Python
Puedes instalarlas mediante APT (evita errores del PEP 668):


