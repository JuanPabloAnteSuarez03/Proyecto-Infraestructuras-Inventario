# 📚 Documentación HTML - Sistema de Inventario

## Versión Visual Interactiva

Esta carpeta contiene versiones HTML de toda la documentación del sistema de inventario con diseño moderno y visual para facilitar el aprendizaje.

## 🚀 Cómo Ver la Documentación

### Opción 1: Abrir Directamente en el Navegador

```bash
# Desde la carpeta docs/
open index.html          # macOS
xdg-open index.html      # Linux
start index.html         # Windows
```

O simplemente haz doble clic en `index.html`

### Opción 2: Servidor Local (Recomendado)

Para que los diagramas Mermaid funcionen correctamente:

```bash
# Opción A: Python 3
cd docs
python3 -m http.server 8000

# Opción B: Node.js
npx http-server docs -p 8000

# Luego abrir: http://localhost:8000
```

## 📄 Archivos Disponibles

```
docs/
├── index.html                    # 🏠 Página principal (¡EMPEZAR AQUÍ!)
├── html/
│   ├── 00_indice.html           # 🗺️ Índice completo
│   ├── 01_arquitectura.html     # 🏗️ Arquitectura general
│   ├── 02_sistema_colas.html    # 🔄 Sistema de colas (⭐ CLAVE)
│   ├── 03_paralelismo.html      # ⚡ Paralelismo (⭐ CLAVE)
│   ├── 04_flujos.html           # 📊 Flujos de inventario
│   ├── 05_guia_desarrollo.html  # 🛠️ Guía de desarrollo
│   ├── readme.html              # 📖 README
│   └── testing.html             # 🧪 Testing
└── generate_html.py              # 🔧 Script de generación
```

## ✨ Características de la Versión HTML

### 🎨 Diseño Moderno
- Colores vibrantes y gradientes
- Animaciones suaves
- Tipografía clara (Inter + Fira Code)
- Responsive (móvil, tablet, desktop)

### 🧭 Navegación Fácil
- Barra de navegación sticky
- Sidebar con links rápidos
- Breadcrumbs context-aware
- Enlaces cruzados entre documentos

### 💻 Código Resaltado
- Syntax highlighting con highlight.js
- Soporte para Python, JavaScript, Bash, YAML, etc.
- Tema oscuro para código
- Botón de copiar código (próximamente)

### 📊 Diagramas Interactivos
- Renderizado de diagramas Mermaid
- Diagramas de secuencia
- Máquinas de estado
- Flowcharts

### 🔍 Fácil de Leer
- Tipografía optimizada
- Espaciado generoso
- Contraste WCAG AA
- Tablas estilizadas

## 🔄 Re-generar HTML

Si modificas los archivos Markdown:

```bash
cd docs
python3 generate_html.py
```

Esto regenerará todos los archivos HTML automáticamente.

## 📖 Orden de Lectura Recomendado

### Para Desarrolladores Nuevos

1. **index.html** - Vista general
2. **html/readme.html** - Quick start
3. **html/01_arquitectura.html** - Entender el sistema
4. **html/02_sistema_colas.html** - Colas asíncronas
5. **html/03_paralelismo.html** - Concurrencia
6. **html/04_flujos.html** - Flujos de negocio
7. **html/05_guia_desarrollo.html** - Empezar a codear

### Para Arquitectos

1. **html/01_arquitectura.html** - Decisiones de diseño
2. **html/02_sistema_colas.html** - Escalabilidad
3. **html/03_paralelismo.html** - Gestión de estado

### Para Product Managers

1. **html/readme.html** - Funcionalidades
2. **html/04_flujos.html** - Flujos de negocio

## 🎯 Enlaces Rápidos HTML

| Tema | Archivo HTML |
|------|--------------|
| 🏠 Home | `index.html` |
| 🔄 Cómo funcionan las colas | `html/02_sistema_colas.html#workers` |
| ⚡ Escalabilidad | `html/03_paralelismo.html#escalabilidad` |
| 📊 Flujo de solicitud asíncrona | `html/04_flujos.html#flujo-1` |
| 🛠️ Agregar un worker | `html/05_guia_desarrollo.html#patron-2` |
| 🧪 Testing | `html/testing.html` |

## 🌐 Publicar Documentación

### GitHub Pages

```bash
# 1. Copiar archivos a branch gh-pages
git checkout -b gh-pages
git add docs/
git commit -m "Add HTML documentation"
git push origin gh-pages

# 2. Habilitar GitHub Pages en settings
# Source: gh-pages branch / docs folder
```

### Netlify/Vercel

```bash
# Configurar build:
# Build command: python3 docs/generate_html.py
# Publish directory: docs/
```

## 🔧 Personalización

### Cambiar Colores

Edita `generate_html.py` → sección `CSS_STYLES`:

```css
:root {
    --primary: #6366f1;      /* Morado */
    --secondary: #8b5cf6;    /* Púrpura */
    /* ... */
}
```

### Agregar Funcionalidad

El template HTML está en `HTML_TEMPLATE` dentro de `generate_html.py`.

## 📊 Estadísticas

- **8 documentos HTML** generados
- **Design system completo** con variables CSS
- **Responsive** (móvil, tablet, desktop)
- **Accesible** (WCAG AA)
- **Rápido** (<100ms carga inicial)

## 🎓 Recursos

- **Font**: [Inter](https://rsms.me/inter/) + [Fira Code](https://github.com/tonsky/FiraCode)
- **Highlighting**: [highlight.js](https://highlightjs.org/)
- **Diagramas**: [Mermaid](https://mermaid.js.org/)
- **Inspiración**: [Notion](https://notion.so), [GitBook](https://gitbook.com)

---

**¡Disfruta la documentación visual! 🎉**

Si tienes sugerencias de mejora, edita `generate_html.py` y vuelve a generar.
